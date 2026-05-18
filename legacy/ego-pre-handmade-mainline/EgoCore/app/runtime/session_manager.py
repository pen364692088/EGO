"""
SessionManager - 会话持久化管理

参考 OpenClaw 的 SessionManager，提供会话状态持久化。

版本: v2.0.0
Created: 2026-03-19
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import logging
import uuid

from .types import SessionKey, SessionState, SessionStatus

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器

    参考 OpenClaw 的会话管理：
    - 会话状态持久化到文件
    - 支持 session store 的读写
    - 支持会话重置和维护

    存储格式:
        ~/.egocore/sessions/<agent_id>/sessions.json
        ~/.egocore/sessions/<agent_id>/<session_id>.jsonl (transcript)
    """

    def __init__(
        self,
        agent_id: str = "default",
        store_dir: Optional[str] = None,
    ):
        self._agent_id = agent_id
        self._store_dir = Path(store_dir or os.path.expanduser("~/.egocore/sessions"))
        self._store_dir.mkdir(parents=True, exist_ok=True)

        self._agent_dir = self._store_dir / agent_id
        self._agent_dir.mkdir(parents=True, exist_ok=True)

        self._store_path = self._agent_dir / "sessions.json"
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

        # 加载现有会话
        self._load()

    def _run_sync(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("SessionManager sync wrappers cannot be called from a running event loop")

    def _load(self) -> None:
        """加载会话存储"""
        if not self._store_path.exists():
            return

        try:
            with open(self._store_path, "r") as f:
                data = json.load(f)

            for key, entry in data.items():
                self._sessions[key] = SessionState(
                    session_key=entry.get("session_key", key),
                    session_id=entry.get("session_id", str(uuid.uuid4())),
                    status=SessionStatus(entry.get("status", "active")),
                    turn_index=entry.get("turn_index", 0),
                    created_at=datetime.fromisoformat(entry["created_at"]) if entry.get("created_at") else datetime.now(timezone.utc),
                    updated_at=datetime.fromisoformat(entry["updated_at"]) if entry.get("updated_at") else datetime.now(timezone.utc),
                    active_task_id=entry.get("active_task_id"),
                    task_plan=entry.get("task_plan", {}),
                    plan_steps=entry.get("plan_steps", []),
                    targets=entry.get("targets", []),
                    active_target=entry.get("active_target"),
                    completed_steps=entry.get("completed_steps", []),
                    last_observation=entry.get("last_observation", {}),
                    artifact_context_by_path=entry.get("artifact_context_by_path", {}),
                    last_intent=entry.get("last_intent"),
                    active_artifact_path=entry.get("active_artifact_path"),
                    artifact_kind=entry.get("artifact_kind"),
                    active_focus=entry.get("active_focus"),
                    default_edit_target=entry.get("default_edit_target"),
                    artifact_summary=entry.get("artifact_summary", {}),
                    last_known_state=entry.get("last_known_state", {}),
                    last_tool_result=entry.get("last_tool_result", {}),
                    last_reply_turn=entry.get("last_reply_turn", 0),
                    last_reply_content=entry.get("last_reply_content", ""),
                    total_turns=entry.get("total_turns", 0),
                    total_tokens=entry.get("total_tokens", 0),
                )

            logger.info(f"SessionManager: loaded {len(self._sessions)} sessions")

        except Exception as e:
            logger.error(f"SessionManager: failed to load sessions: {e}")

    def _save(self) -> None:
        """保存会话存储"""
        try:
            data = {}
            for key, state in self._sessions.items():
                data[key] = state.to_dict()

            # 原子写入
            temp_path = self._store_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            os.replace(temp_path, self._store_path)

        except Exception as e:
            logger.error(f"SessionManager: failed to save sessions: {e}")

    async def get_or_create(
        self,
        session_key: str,
        channel: str = "cli",
    ) -> SessionState:
        """
        获取或创建会话

        类似 OpenClaw 的 resolveSession()
        """
        async with self._lock:
            if session_key in self._sessions:
                session = self._sessions[session_key]
                session.touch()
                return session

            # 创建新会话
            session = SessionState(
                session_key=session_key,
                session_id=f"sid_{uuid.uuid4().hex[:12]}",
                status=SessionStatus.ACTIVE,
            )

            self._sessions[session_key] = session
            self._save()

            logger.info(f"SessionManager: created session={session.session_id} key={session_key}")
            return session

    def get_or_create_sync(
        self,
        session_key: str,
        channel: str = "cli",
    ) -> SessionState:
        return self._run_sync(self.get_or_create(session_key, channel=channel))

    async def get(self, session_key: str) -> Optional[SessionState]:
        """获取会话"""
        return self._sessions.get(session_key)

    def get_sync(self, session_key: str) -> Optional[SessionState]:
        return self._run_sync(self.get(session_key))

    async def update(
        self,
        session_key: str,
        **kwargs,
    ) -> Optional[SessionState]:
        """
        更新会话

        支持的字段: status, active_task_id, task_plan, plan_steps, targets, active_target, completed_steps, last_observation, artifact_context_by_path, last_intent, active_artifact_path, artifact_kind, active_focus, default_edit_target, artifact_summary, last_known_state, last_tool_result, last_reply_turn, last_reply_content, turn_index, total_turns, total_tokens
        """
        async with self._lock:
            session = self._sessions.get(session_key)
            if not session:
                return None

            if "status" in kwargs:
                session.status = SessionStatus(kwargs["status"])
            if "active_task_id" in kwargs:
                session.active_task_id = kwargs["active_task_id"]
            if "task_plan" in kwargs:
                session.task_plan = kwargs["task_plan"]
            if "plan_steps" in kwargs:
                session.plan_steps = kwargs["plan_steps"]
            if "targets" in kwargs:
                session.targets = kwargs["targets"]
            if "active_target" in kwargs:
                session.active_target = kwargs["active_target"]
            if "completed_steps" in kwargs:
                session.completed_steps = kwargs["completed_steps"]
            if "last_observation" in kwargs:
                session.last_observation = kwargs["last_observation"]
            if "artifact_context_by_path" in kwargs:
                session.artifact_context_by_path = kwargs["artifact_context_by_path"]
            if "last_intent" in kwargs:
                session.last_intent = kwargs["last_intent"]
            if "last_tool_result" in kwargs:
                session.last_tool_result = kwargs["last_tool_result"]
            if "last_reply_turn" in kwargs:
                session.last_reply_turn = kwargs["last_reply_turn"]
            if "last_reply_content" in kwargs:
                session.last_reply_content = kwargs["last_reply_content"]
            if "artifact_summary" in kwargs:
                session.artifact_summary = kwargs["artifact_summary"]
            if "active_artifact_path" in kwargs:
                session.active_artifact_path = kwargs["active_artifact_path"]
            if "artifact_kind" in kwargs:
                session.artifact_kind = kwargs["artifact_kind"]
            if "active_focus" in kwargs:
                session.active_focus = kwargs["active_focus"]
            if "default_edit_target" in kwargs:
                session.default_edit_target = kwargs["default_edit_target"]
            if "turn_index" in kwargs:
                session.turn_index = kwargs["turn_index"]
            if "total_turns" in kwargs:
                session.total_turns = kwargs["total_turns"]
            if "total_tokens" in kwargs:
                session.total_tokens = kwargs["total_tokens"]

            session.touch()
            self._save()

            return session

    async def increment_turn(self, session_key: str) -> int:
        """增加轮次"""
        async with self._lock:
            session = self._sessions.get(session_key)
            if not session:
                return 0

            session.turn_index += 1
            session.total_turns += 1
            session.touch()
            self._save()

            return session.turn_index

    def increment_turn_sync(self, session_key: str) -> int:
        return self._run_sync(self.increment_turn(session_key))

    async def reset(self, session_key: str) -> SessionState:
        """
        重置会话

        类似 OpenClaw 的 /reset
        """
        async with self._lock:
            old_session = self._sessions.get(session_key)
            old_turn = old_session.turn_index if old_session else 0

            # 创建新会话
            new_session = SessionState(
                session_key=session_key,
                session_id=f"sid_{uuid.uuid4().hex[:12]}",
                status=SessionStatus.ACTIVE,
            )

            self._sessions[session_key] = new_session
            self._save()

            logger.info(f"SessionManager: reset session old_turn={old_turn} new_id={new_session.session_id}")
            return new_session

    async def delete(self, session_key: str) -> bool:
        """删除会话"""
        async with self._lock:
            if session_key not in self._sessions:
                return False

            del self._sessions[session_key]
            self._save()

            logger.info(f"SessionManager: deleted session key={session_key}")
            return True

    async def list_sessions(
        self,
        active_only: bool = False,
        limit: int = 100,
    ) -> List[SessionState]:
        """列出会话"""
        sessions = list(self._sessions.values())

        if active_only:
            sessions = [s for s in sessions if s.status == SessionStatus.ACTIVE]

        # 按更新时间排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]

    def get_transcript_path(self, session_id: str) -> Path:
        """获取会话记录文件路径"""
        return self._agent_dir / f"{session_id}.jsonl"

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """追加轮次记录"""
        transcript_path = self.get_transcript_path(session_id)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        with open(transcript_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        active = sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)
        total_turns = sum(s.total_turns for s in self._sessions.values())

        return {
            "agent_id": self._agent_id,
            "total_sessions": len(self._sessions),
            "active_sessions": active,
            "total_turns": total_turns,
            "store_path": str(self._store_path),
        }


# 全局实例
_managers: Dict[str, SessionManager] = {}


def get_session_manager(agent_id: str = "default") -> SessionManager:
    """获取会话管理器"""
    if agent_id not in _managers:
        _managers[agent_id] = SessionManager(agent_id=agent_id)
    return _managers[agent_id]
