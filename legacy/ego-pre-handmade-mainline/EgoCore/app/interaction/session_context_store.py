"""
Session Context Store - EgoCore

存储最近对话上下文，用于主体解释。

简单实现：内存存储，按 session_id 隔离。
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict
import threading


class SessionContextStore:
    """
    会话上下文存储
    
    存储最近 N 轮对话，用于主体解释时识别上下文。
    """
    
    def __init__(self, max_turns_per_session: int = 10):
        self._max_turns = max_turns_per_session
        self._store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._turn_index: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """添加一轮对话"""
        with self._lock:
            turn = {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._store[session_id].append(turn)
            
            # 增加轮次索引
            if role == "user":
                self._turn_index[session_id] += 1
            
            # 保持最近 N 轮
            if len(self._store[session_id]) > self._max_turns:
                self._store[session_id] = self._store[session_id][-self._max_turns:]
    
    def get_turn_index(self, session_id: str) -> int:
        """获取当前会话轮次索引"""
        with self._lock:
            return self._turn_index.get(session_id, 0)
    
    def get_recent_turns(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取最近对话"""
        with self._lock:
            turns = self._store.get(session_id, [])
            if limit:
                return turns[-limit:]
            return turns.copy()
    
    def clear_session(self, session_id: str) -> None:
        """清除会话"""
        with self._lock:
            self._store.pop(session_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_sessions": len(self._store),
                "sessions": {
                    sid: len(turns) 
                    for sid, turns in self._store.items()
                }
            }


# 全局实例
_store: Optional[SessionContextStore] = None


def get_session_context_store() -> SessionContextStore:
    """获取全局会话上下文存储"""
    global _store
    if _store is None:
        _store = SessionContextStore()
    return _store
