"""
LaneManager - 队列串行化管理

参考 OpenClaw 的 lane 机制，保证同一 session 的任务串行执行。

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class LaneTask:
    """Lane 任务"""
    task_id: str
    lane_key: str
    coro: Callable[[], Awaitable[Any]]
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None


@dataclass
class LaneState:
    """Lane 状态"""
    lane_key: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    current_task: Optional[LaneTask] = None
    is_processing: bool = False
    total_tasks: int = 0
    completed_tasks: int = 0


class LaneManager:
    """
    Lane 管理器
    
    参考 OpenClaw 的 resolveSessionLane() 和队列机制：
    - 同一 session 的任务串行执行
    - 不同 session 可以并行
    - 支持全局 lane 限制并发
    
    用法:
        lane_manager = LaneManager()
        await lane_manager.enqueue(session_key, my_coro)
    """
    
    def __init__(
        self,
        max_concurrent_per_lane: int = 1,
        max_concurrent_global: int = 10,
    ):
        self._max_concurrent_per_lane = max_concurrent_per_lane
        self._max_concurrent_global = max_concurrent_global
        
        self._lanes: Dict[str, LaneState] = {}
        self._tasks: Dict[str, LaneTask] = {}
        self._global_semaphore = asyncio.Semaphore(max_concurrent_global)
        self._lock = asyncio.Lock()
        
        # 统计
        self._total_enqueued = 0
        self._total_completed = 0
    
    def resolve_lane_key(self, session_key: str) -> str:
        """
        解析 lane key
        
        类似 OpenClaw 的 resolveSessionLane()
        """
        if session_key.startswith("lane:"):
            return session_key
        return f"lane:{session_key}"
    
    async def enqueue(
        self,
        session_key: str,
        coro: Callable[[], Awaitable[Any]],
        priority: int = 1,
    ) -> str:
        """
        将任务加入队列
        
        Args:
            session_key: 会话 key
            coro: 协程函数
            priority: 优先级 (越小越高)
        
        Returns:
            task_id
        """
        lane_key = self.resolve_lane_key(session_key)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        task = LaneTask(
            task_id=task_id,
            lane_key=lane_key,
            coro=coro,
            priority=priority,
        )
        
        async with self._lock:
            if lane_key not in self._lanes:
                self._lanes[lane_key] = LaneState(lane_key=lane_key)
            
            lane = self._lanes[lane_key]
            self._tasks[task_id] = task
            await lane.queue.put(task)
            lane.total_tasks += 1
            self._total_enqueued += 1
        
        logger.debug(f"LaneManager: enqueued task={task_id} lane={lane_key}")
        
        # 启动处理
        asyncio.create_task(self._process_lane(lane_key))
        
        return task_id
    
    async def _process_lane(self, lane_key: str) -> None:
        """处理 lane 队列"""
        async with self._lock:
            lane = self._lanes.get(lane_key)
            if not lane or lane.is_processing:
                return
            lane.is_processing = True
        
        try:
            while True:
                lane = self._lanes.get(lane_key)
                if not lane:
                    break
                
                try:
                    # 等待任务 (带超时)
                    task = await asyncio.wait_for(lane.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # 没有更多任务
                    break
                
                # 全局并发限制
                async with self._global_semaphore:
                    await self._execute_task(task, lane)
        
        finally:
            async with self._lock:
                lane = self._lanes.get(lane_key)
                if lane:
                    lane.is_processing = False
    
    async def _execute_task(self, task: LaneTask, lane: LaneState) -> None:
        """执行单个任务"""
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        lane.current_task = task
        
        logger.info(f"LaneManager: executing task={task.task_id} lane={lane.lane_key}")
        
        try:
            result = await task.coro()
            task.result = result
            task.status = "completed"
            lane.completed_tasks += 1
            self._total_completed += 1
            
            logger.info(f"LaneManager: completed task={task.task_id}")
            
        except asyncio.CancelledError:
            task.status = "cancelled"
            logger.warning(f"LaneManager: cancelled task={task.task_id}")
            raise
        
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"LaneManager: failed task={task.task_id}: {e}")
        
        finally:
            task.completed_at = datetime.now(timezone.utc)
            lane.current_task = None
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout_ms: int = 30000,
    ) -> Optional[LaneTask]:
        """
        等待任务完成
        
        Args:
            task_id: 任务 ID
            timeout_ms: 超时时间 (毫秒)
        
        Returns:
            LaneTask 或 None
        """
        start = datetime.now(timezone.utc)
        timeout_sec = timeout_ms / 1000
        
        while True:
            # 直接从任务索引查找（包含已完成任务）
            task = self._tasks.get(task_id)
            if task and task.status in ("completed", "failed", "cancelled"):
                return task
            
            # 检查超时
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed >= timeout_sec:
                return None
            
            await asyncio.sleep(0.1)
    
    def get_lane_status(self, lane_key: str) -> Optional[Dict[str, Any]]:
        """获取 lane 状态"""
        lane = self._lanes.get(lane_key)
        if not lane:
            return None
        
        return {
            "lane_key": lane.lane_key,
            "is_processing": lane.is_processing,
            "queue_size": lane.queue.qsize(),
            "current_task": lane.current_task.task_id if lane.current_task else None,
            "total_tasks": lane.total_tasks,
            "completed_tasks": lane.completed_tasks,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_lanes": len(self._lanes),
            "total_enqueued": self._total_enqueued,
            "total_completed": self._total_completed,
            "max_concurrent_per_lane": self._max_concurrent_per_lane,
            "max_concurrent_global": self._max_concurrent_global,
        }
    
    async def abort_lane(self, lane_key: str) -> int:
        """
        中止 lane 中的所有任务
        
        Returns:
            被中止的任务数
        """
        count = 0
        async with self._lock:
            lane = self._lanes.get(lane_key)
            if not lane:
                return 0
            
            # 清空队列
            while not lane.queue.empty():
                try:
                    lane.queue.get_nowait()
                    count += 1
                except asyncio.QueueEmpty:
                    break
            
            # 中止当前任务
            if lane.current_task:
                lane.current_task.status = "cancelled"
                count += 1
        
        logger.info(f"LaneManager: aborted {count} tasks in lane={lane_key}")
        return count


# 全局实例
_lane_manager: Optional[LaneManager] = None


def get_lane_manager() -> LaneManager:
    """获取全局 Lane 管理器"""
    global _lane_manager
    if _lane_manager is None:
        _lane_manager = LaneManager()
    return _lane_manager


async def enqueue_in_lane(
    session_key: str,
    coro: Callable[[], Awaitable[Any]],
    priority: int = 1,
) -> str:
    """
    便捷函数：将任务加入 lane
    
    类似 OpenClaw 的 enqueueCommandInLane()
    """
    return await get_lane_manager().enqueue(session_key, coro, priority)
