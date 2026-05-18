"""
RepairContextManager - 修复上下文管理器

职责:
- 追踪失败任务
- 关联用户反馈（"文件不存在"）
- 生成 repair_context
- 挂载到上一轮任务

版本: v1.0.0
Created: 2026-03-19
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class FailureRecord:
    """失败记录"""
    task_id: str
    session_id: str
    user_id: str
    task_goal: str
    failure_reason: str
    failure_time: datetime
    execution_result: Optional[Dict[str, Any]] = None
    user_feedback: Optional[str] = None
    retry_count: int = 0
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "task_goal": self.task_goal,
            "failure_reason": self.failure_reason,
            "failure_time": self.failure_time.isoformat(),
            "user_feedback": self.user_feedback,
            "retry_count": self.retry_count,
            "resolved": self.resolved,
        }


@dataclass
class RepairContext:
    """修复上下文"""
    has_pending_repair: bool = False
    failed_task_id: Optional[str] = None
    failure_reason: Optional[str] = None
    user_feedback: Optional[str] = None
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    repair_suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pending_repair": self.has_pending_repair,
            "failed_task_id": self.failed_task_id,
            "failure_reason": self.failure_reason,
            "user_feedback": self.user_feedback,
            "retry_count": self.retry_count,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "repair_suggestions": self.repair_suggestions,
        }


class RepairContextManager:
    """
    修复上下文管理器
    
    功能:
    - 记录失败任务
    - 检测用户反馈中的失败指示
    - 生成 repair_context
    - 追踪重试
    """
    
    # 用户反馈中的失败指示关键词
    FAILURE_INDICATORS = [
        "并不存在", "不存在", "没有", "没找到", "找不到",
        "失败了", "报错", "错误", "不行", "不对",
        "doesn't exist", "not found", "failed", "error",
    ]
    
    def __init__(self, max_failures_per_session: int = 10):
        self._max_failures = max_failures_per_session
        self._failures: Dict[str, List[FailureRecord]] = defaultdict(list)
        self._pending_repairs: Dict[str, FailureRecord] = {}
        self._lock = threading.Lock()
    
    def record_failure(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
        task_goal: str,
        failure_reason: str,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> FailureRecord:
        """
        记录失败任务
        
        Args:
            task_id: 任务 ID
            session_id: 会话 ID
            user_id: 用户 ID
            task_goal: 任务目标
            failure_reason: 失败原因
            execution_result: 执行结果
        
        Returns:
            FailureRecord
        """
        record = FailureRecord(
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            task_goal=task_goal,
            failure_reason=failure_reason,
            failure_time=datetime.now(timezone.utc),
            execution_result=execution_result,
        )
        
        with self._lock:
            key = f"{session_id}:{user_id}"
            self._failures[key].append(record)
            
            # 限制存储数量
            if len(self._failures[key]) > self._max_failures:
                self._failures[key] = self._failures[key][-self._max_failures:]
            
            # 设置为待修复
            self._pending_repairs[key] = record
        
        logger.info(
            f"RepairContextManager: recorded failure "
            f"task={task_id}, session={session_id}, reason={failure_reason}"
        )
        
        return record
    
    def detect_user_feedback(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
    ) -> Optional[FailureRecord]:
        """
        检测用户反馈中的失败指示
        
        Args:
            user_input: 用户输入
            session_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            如果检测到失败指示，返回相关失败记录
        """
        user_lower = user_input.lower()
        
        # 检查是否包含失败指示
        has_failure_indicator = False
        for indicator in self.FAILURE_INDICATORS:
            if indicator in user_lower:
                has_failure_indicator = True
                break
        
        if not has_failure_indicator:
            return None
        
        # 查找最近的失败记录
        key = f"{session_id}:{user_id}"
        with self._lock:
            failures = self._failures.get(key, [])
            if failures:
                latest = failures[-1]
                # 关联用户反馈
                latest.user_feedback = user_input
                logger.info(
                    f"RepairContextManager: detected failure feedback "
                    f"task={latest.task_id}, feedback={user_input[:50]}"
                )
                return latest
        
        return None
    
    def get_pending_repair(
        self,
        session_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取待修复上下文
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            待修复信息或 None
        """
        key = f"{session_id}:{user_id}"
        with self._lock:
            record = self._pending_repairs.get(key)
            if record and not record.resolved:
                return record.to_dict()
        return None
    
    def get_repair_context(
        self,
        session_id: str,
        user_id: str,
    ) -> RepairContext:
        """
        获取修复上下文
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            RepairContext
        """
        key = f"{session_id}:{user_id}"
        with self._lock:
            record = self._pending_repairs.get(key)
            if record and not record.resolved:
                suggestions = self._generate_repair_suggestions(record)
                return RepairContext(
                    has_pending_repair=True,
                    failed_task_id=record.task_id,
                    failure_reason=record.failure_reason,
                    user_feedback=record.user_feedback,
                    retry_count=record.retry_count,
                    last_attempt=record.failure_time,
                    repair_suggestions=suggestions,
                )
        
        return RepairContext()
    
    def mark_resolved(
        self,
        session_id: str,
        user_id: str,
    ) -> bool:
        """
        标记修复已解决
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            是否成功标记
        """
        key = f"{session_id}:{user_id}"
        with self._lock:
            record = self._pending_repairs.get(key)
            if record:
                record.resolved = True
                del self._pending_repairs[key]
                logger.info(
                    f"RepairContextManager: marked resolved "
                    f"task={record.task_id}, session={session_id}"
                )
                return True
        return False
    
    def increment_retry(
        self,
        session_id: str,
        user_id: str,
    ) -> int:
        """
        增加重试计数
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            新的重试计数
        """
        key = f"{session_id}:{user_id}"
        with self._lock:
            record = self._pending_repairs.get(key)
            if record:
                record.retry_count += 1
                return record.retry_count
        return 0
    
    def _generate_repair_suggestions(self, record: FailureRecord) -> List[str]:
        """生成修复建议"""
        suggestions = []
        
        reason_lower = record.failure_reason.lower()
        
        # 根据失败原因生成建议
        if "file" in reason_lower or "文件" in reason_lower:
            suggestions.append("检查文件路径是否正确")
            suggestions.append("确认是否有写入权限")
        
        if "not found" in reason_lower or "不存在" in reason_lower:
            suggestions.append("确认目标是否已创建")
            suggestions.append("检查路径拼写")
        
        if "permission" in reason_lower or "权限" in reason_lower:
            suggestions.append("检查文件权限")
            suggestions.append("可能需要提升权限")
        
        if "timeout" in reason_lower or "超时" in reason_lower:
            suggestions.append("尝试增加超时时间")
            suggestions.append("检查网络连接")
        
        # 如果有用户反馈，添加针对性建议
        if record.user_feedback:
            if "不存在" in record.user_feedback:
                suggestions.append(f"上一轮操作可能未成功，需要重新执行: {record.task_goal[:50]}")
        
        if not suggestions:
            suggestions.append("重新执行任务")
        
        return suggestions
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total_failures = sum(len(f) for f in self._failures.values())
            pending_repairs = len(self._pending_repairs)
            
            return {
                "total_failures": total_failures,
                "pending_repairs": pending_repairs,
                "sessions_with_failures": len(self._failures),
            }


# 全局实例
_manager: Optional[RepairContextManager] = None


def get_repair_context_manager() -> RepairContextManager:
    """获取全局修复上下文管理器"""
    global _manager
    if _manager is None:
        _manager = RepairContextManager()
    return _manager


def record_failure(
    task_id: str,
    session_id: str,
    user_id: str,
    task_goal: str,
    failure_reason: str,
    execution_result: Optional[Dict[str, Any]] = None,
) -> FailureRecord:
    """
    便捷函数：记录失败
    """
    return get_repair_context_manager().record_failure(
        task_id=task_id,
        session_id=session_id,
        user_id=user_id,
        task_goal=task_goal,
        failure_reason=failure_reason,
        execution_result=execution_result,
    )


def get_repair_context(session_id: str, user_id: str) -> RepairContext:
    """
    便捷函数：获取修复上下文
    """
    return get_repair_context_manager().get_repair_context(session_id, user_id)
