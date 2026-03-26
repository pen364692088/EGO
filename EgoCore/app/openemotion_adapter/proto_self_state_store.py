"""
Proto-Self host-side state store.

分层目标：
- agent-global: OpenEmotion ProtoSelfState 的宿主镜像/缓存
- session: 宿主运行时 session 元数据与 reset 审计
- thread: 会话线程绑定与最近事件指针
- experiment(run): replay / experiment 的隔离状态副本

设计约束：
- EgoCore 只保存宿主侧镜像、索引和审计，不定义主体本体语义
- OpenEmotion 仍是 ProtoSelfState 字段语义权威源
- 保留 legacy `artifacts/proto_self_mirror/state.json` 兼容写入
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from openemotion.proto_self import ProtoSelfState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_scope_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "unknown"


class ProtoSelfStateStore:
    """Host-side layered store for Proto-Self mirror state."""

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        legacy_mirror_dir: Optional[Path] = None,
    ) -> None:
        self.root_dir = root_dir or Path("artifacts/proto_self_store")
        self.legacy_mirror_dir = legacy_mirror_dir or Path("artifacts/proto_self_mirror")
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_mirror_dir.mkdir(parents=True, exist_ok=True)

    @property
    def agent_global_dir(self) -> Path:
        path = self.root_dir / "agent_global"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def agent_global_state_path(self) -> Path:
        return self.agent_global_dir / "proto_self_state.v1.json"

    @property
    def legacy_state_path(self) -> Path:
        return self.legacy_mirror_dir / "state.json"

    def _session_dir(self, session_id: str) -> Path:
        path = self.root_dir / "sessions" / _sanitize_scope_id(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _thread_dir(self, thread_id: str) -> Path:
        path = self.root_dir / "threads" / _sanitize_scope_id(thread_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _experiment_dir(self, experiment_id: str) -> Path:
        path = self.root_dir / "experiments" / _sanitize_scope_id(experiment_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def _resolve_scope(self, context: Optional[Dict[str, Any]]) -> tuple[str, Optional[str]]:
        context = context or {}
        scope = context.get("state_scope")
        experiment_id = context.get("experiment_id")
        if scope == "experiment" and experiment_id:
            return "experiment", experiment_id
        return "agent_global", None

    def load_state(self, context: Optional[Dict[str, Any]] = None) -> ProtoSelfState:
        scope, experiment_id = self._resolve_scope(context)
        if scope == "experiment" and experiment_id:
            return self.load_experiment_state(experiment_id)
        return self.load_agent_global_state()

    def save_state(self, state: ProtoSelfState, context: Optional[Dict[str, Any]] = None) -> None:
        scope, experiment_id = self._resolve_scope(context)
        if scope == "experiment" and experiment_id:
            self.save_experiment_state(experiment_id, state)
            return
        self.save_agent_global_state(state, context=context)

    def load_agent_global_state(self) -> ProtoSelfState:
        data = self._read_json(self.agent_global_state_path)
        if data is not None:
            return ProtoSelfState.from_dict(data)
        legacy = self._read_json(self.legacy_state_path)
        if legacy is not None:
            return ProtoSelfState.from_dict(legacy)
        return ProtoSelfState.empty()

    def save_agent_global_state(
        self,
        state: ProtoSelfState,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = state.to_dict()
        self._write_json(self.agent_global_state_path, payload)
        # Compatibility-only mirror for existing scripts and current mainline wiring.
        self._write_json(self.legacy_state_path, payload)
        metadata = {
            "scope": "agent_global",
            "updated_at": _now_iso(),
            "authority": "openemotion.proto_self",
            "host_role": "mirror_cache",
            "last_context": context or {},
        }
        self._write_json(self.agent_global_dir / "manifest.json", metadata)

    def record_event_binding(
        self,
        *,
        session_id: str,
        thread_id: Optional[str],
        source: str,
        event_id: str,
        turn_id: Optional[str],
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = _now_iso()
        resolved_thread_id = thread_id or session_id
        session_manifest_path = self._session_dir(session_id) / "session.json"
        thread_manifest_path = self._thread_dir(resolved_thread_id) / "thread.json"

        session_manifest = self._read_json(session_manifest_path) or {
            "session_id": session_id,
            "scope": "session",
            "created_at": now,
            "reset_count": 0,
        }
        session_manifest.update(
            {
                "updated_at": now,
                "thread_id": resolved_thread_id,
                "source": source,
                "latest_event_id": event_id,
                "latest_turn_id": turn_id,
                "latest_event_type": event_type,
            }
        )
        self._write_json(session_manifest_path, session_manifest)

        thread_manifest = self._read_json(thread_manifest_path) or {
            "thread_id": resolved_thread_id,
            "scope": "thread",
            "created_at": now,
            "event_count": 0,
        }
        thread_manifest.update(
            {
                "updated_at": now,
                "source": source,
                "latest_session_id": session_id,
                "latest_event_id": event_id,
                "latest_turn_id": turn_id,
                "latest_event_type": event_type,
            }
        )
        thread_manifest["event_count"] = int(thread_manifest.get("event_count", 0)) + 1
        if context:
            thread_manifest["last_context"] = context
        self._write_json(thread_manifest_path, thread_manifest)

    def record_session_reset(
        self,
        *,
        session_id: str,
        thread_id: Optional[str] = None,
        source: str = "host",
        command: str = "reset_session",
        generation_id: Optional[int] = None,
    ) -> None:
        now = _now_iso()
        session_manifest_path = self._session_dir(session_id) / "session.json"
        session_manifest = self._read_json(session_manifest_path) or {
            "session_id": session_id,
            "scope": "session",
            "created_at": now,
            "reset_count": 0,
        }
        session_manifest["updated_at"] = now
        session_manifest["source"] = source
        session_manifest["thread_id"] = thread_id or session_manifest.get("thread_id") or session_id
        session_manifest["reset_count"] = int(session_manifest.get("reset_count", 0)) + 1
        session_manifest["last_reset"] = {
            "command": command,
            "at": now,
            "preserves_agent_global": True,
            "preserves_thread_history": True,
        }
        if generation_id is not None:
            session_manifest["generation_id"] = generation_id
        self._write_json(session_manifest_path, session_manifest)

    def fork_experiment(
        self,
        experiment_id: str,
        *,
        source_trace: Optional[str] = None,
        base_state: Optional[ProtoSelfState] = None,
    ) -> None:
        state = base_state or self.load_agent_global_state()
        experiment_dir = self._experiment_dir(experiment_id)
        manifest = {
            "experiment_id": experiment_id,
            "scope": "experiment",
            "created_at": _now_iso(),
            "source_trace": source_trace,
            "base_scope": "agent_global",
            "host_role": "isolated_replay_run",
        }
        self._write_json(experiment_dir / "manifest.json", manifest)
        self._write_json(experiment_dir / "proto_self_state.v1.json", deepcopy(state.to_dict()))

    def load_experiment_state(self, experiment_id: str) -> ProtoSelfState:
        path = self._experiment_dir(experiment_id) / "proto_self_state.v1.json"
        data = self._read_json(path)
        if data is None:
            self.fork_experiment(experiment_id)
            data = self._read_json(path) or ProtoSelfState.empty().to_dict()
        return ProtoSelfState.from_dict(data)

    def save_experiment_state(self, experiment_id: str, state: ProtoSelfState) -> None:
        experiment_dir = self._experiment_dir(experiment_id)
        manifest = self._read_json(experiment_dir / "manifest.json") or {
            "experiment_id": experiment_id,
            "scope": "experiment",
            "created_at": _now_iso(),
            "base_scope": "agent_global",
            "host_role": "isolated_replay_run",
        }
        manifest["updated_at"] = _now_iso()
        self._write_json(experiment_dir / "manifest.json", manifest)
        self._write_json(experiment_dir / "proto_self_state.v1.json", state.to_dict())
