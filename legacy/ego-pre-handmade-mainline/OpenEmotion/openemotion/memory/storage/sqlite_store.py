"""
Memory SQLite Store v1

统一的记忆存储层，支持：
- SQLite 持久化
- 多用户隔离
- trace_id 审计
- 重启恢复

架构要求：
- 主隔离维度: user_id
- 辅助隔离维度: identity_handle
- 审计维度: trace_id, case_id
"""

import json
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
import aiosqlite


@dataclass
class MemoryEvent:
    """记忆事件"""
    id: str
    user_id: str
    identity_handle: str
    trace_id: str
    case_id: str
    session_epoch: str
    timestamp: float
    event_type: str
    payload: Dict[str, Any]
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryNarrative:
    """记忆叙事"""
    id: str
    user_id: str
    trace_id: str
    case_id: str
    source_event_ids: List[str]
    theme: str
    summary: str
    confidence: float
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryPolicy:
    """记忆策略"""
    id: str
    user_id: str
    trace_id: str
    case_id: str
    source_narrative_ids: List[str]
    policy_key: str
    policy_value: str
    confidence: float
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemorySQLiteStore:
    """
    记忆系统 SQLite 存储层
    
    功能：
    - 事件/叙事/策略三层存储
    - 多用户隔离
    - trace_id 审计
    - 重启恢复
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "./data/memory_store.db"
        self._initialized = False
        
        # 统计
        self.stats = {
            "events_written": 0,
            "narratives_written": 0,
            "policies_written": 0,
            "events_read": 0,
            "narratives_read": 0,
            "policies_read": 0,
            "errors": 0,
        }
    
    async def init_db(self) -> None:
        """初始化数据库"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Events 表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    identity_handle TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    session_epoch TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 索引
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_user_id 
                ON memory_events(user_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_trace_id 
                ON memory_events(trace_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_case_id 
                ON memory_events(case_id)
            """)
            
            # Narratives 表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_narratives (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    source_event_ids TEXT NOT NULL,
                    theme TEXT,
                    summary TEXT,
                    confidence REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_narratives_user_id 
                ON memory_narratives(user_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_narratives_trace_id 
                ON memory_narratives(trace_id)
            """)
            
            # Policies 表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_policies (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    source_narrative_ids TEXT NOT NULL,
                    policy_key TEXT NOT NULL,
                    policy_value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_policies_user_id 
                ON memory_policies(user_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_policies_trace_id 
                ON memory_policies(trace_id)
            """)
            
            await db.commit()
        
        self._initialized = True
    
    # ========== Events ==========
    
    async def write_event(self, event: MemoryEvent) -> str:
        """写入事件"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO memory_events
                (id, user_id, identity_handle, trace_id, case_id, session_epoch,
                 timestamp, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id,
                event.user_id,
                event.identity_handle,
                event.trace_id,
                event.case_id,
                event.session_epoch,
                event.timestamp,
                event.event_type,
                json.dumps(event.payload),
                event.created_at,
            ))
            await db.commit()
        
        self.stats["events_written"] += 1
        return event.id
    
    async def read_event(self, event_id: str) -> Optional[MemoryEvent]:
        """读取单个事件"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM memory_events WHERE id = ?", (event_id,)
            )
            row = await cursor.fetchone()
        
        if row:
            self.stats["events_read"] += 1
            return self._row_to_event(row)
        return None
    
    async def query_events_by_user(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[MemoryEvent]:
        """按用户查询事件"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM memory_events 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = await cursor.fetchall()
        
        self.stats["events_read"] += len(rows)
        return [self._row_to_event(row) for row in rows]
    
    async def query_events_by_trace(self, trace_id: str) -> List[MemoryEvent]:
        """按 trace_id 查询事件"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM memory_events 
                WHERE trace_id = ? 
                ORDER BY timestamp ASC
                """,
                (trace_id,)
            )
            rows = await cursor.fetchall()
        
        self.stats["events_read"] += len(rows)
        return [self._row_to_event(row) for row in rows]
    
    def _row_to_event(self, row) -> MemoryEvent:
        """行转事件"""
        return MemoryEvent(
            id=row[0],
            user_id=row[1],
            identity_handle=row[2],
            trace_id=row[3],
            case_id=row[4],
            session_epoch=row[5],
            timestamp=row[6],
            event_type=row[7],
            payload=json.loads(row[8]),
            created_at=row[9],
        )
    
    # ========== Narratives ==========
    
    async def write_narrative(self, narrative: MemoryNarrative) -> str:
        """写入叙事"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO memory_narratives
                (id, user_id, trace_id, case_id, source_event_ids, theme, 
                 summary, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                narrative.id,
                narrative.user_id,
                narrative.trace_id,
                narrative.case_id,
                json.dumps(narrative.source_event_ids),
                narrative.theme,
                narrative.summary,
                narrative.confidence,
                narrative.created_at,
                narrative.updated_at,
            ))
            await db.commit()
        
        self.stats["narratives_written"] += 1
        return narrative.id
    
    async def read_narrative(self, narrative_id: str) -> Optional[MemoryNarrative]:
        """读取单个叙事"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM memory_narratives WHERE id = ?", (narrative_id,)
            )
            row = await cursor.fetchone()
        
        if row:
            self.stats["narratives_read"] += 1
            return self._row_to_narrative(row)
        return None
    
    async def query_narratives_by_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[MemoryNarrative]:
        """按用户查询叙事"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM memory_narratives 
                WHERE user_id = ? 
                ORDER BY updated_at DESC 
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = await cursor.fetchall()
        
        self.stats["narratives_read"] += len(rows)
        return [self._row_to_narrative(row) for row in rows]
    
    async def get_latest_narrative_for_user(self, user_id: str) -> Optional[MemoryNarrative]:
        """获取用户最新叙事"""
        narratives = await self.query_narratives_by_user(user_id, limit=1)
        return narratives[0] if narratives else None
    
    def _row_to_narrative(self, row) -> MemoryNarrative:
        """行转叙事"""
        return MemoryNarrative(
            id=row[0],
            user_id=row[1],
            trace_id=row[2],
            case_id=row[3],
            source_event_ids=json.loads(row[4]),
            theme=row[5] or "",
            summary=row[6] or "",
            confidence=row[7],
            created_at=row[8],
            updated_at=row[9],
        )
    
    # ========== Policies ==========
    
    async def write_policy(self, policy: MemoryPolicy) -> str:
        """写入策略"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO memory_policies
                (id, user_id, trace_id, case_id, source_narrative_ids, 
                 policy_key, policy_value, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy.id,
                policy.user_id,
                policy.trace_id,
                policy.case_id,
                json.dumps(policy.source_narrative_ids),
                policy.policy_key,
                policy.policy_value,
                policy.confidence,
                policy.created_at,
                policy.updated_at,
            ))
            await db.commit()
        
        self.stats["policies_written"] += 1
        return policy.id
    
    async def query_policies_by_user(
        self,
        user_id: str,
        policy_key: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryPolicy]:
        """按用户查询策略"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            if policy_key:
                cursor = await db.execute(
                    """
                    SELECT * FROM memory_policies 
                    WHERE user_id = ? AND policy_key = ?
                    ORDER BY updated_at DESC 
                    LIMIT ?
                    """,
                    (user_id, policy_key, limit)
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM memory_policies 
                    WHERE user_id = ? 
                    ORDER BY updated_at DESC 
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
            rows = await cursor.fetchall()
        
        self.stats["policies_read"] += len(rows)
        return [self._row_to_policy(row) for row in rows]
    
    def _row_to_policy(self, row) -> MemoryPolicy:
        """行转策略"""
        return MemoryPolicy(
            id=row[0],
            user_id=row[1],
            trace_id=row[2],
            case_id=row[3],
            source_narrative_ids=json.loads(row[4]),
            policy_key=row[5],
            policy_value=row[6],
            confidence=row[7],
            created_at=row[8],
            updated_at=row[9],
        )
    
    # ========== 统计与维护 ==========
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            event_count = await self._count_table(db, "memory_events")
            narrative_count = await self._count_table(db, "memory_narratives")
            policy_count = await self._count_table(db, "memory_policies")
            
            # 用户数
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM memory_events"
            )
            user_count = (await cursor.fetchone())[0]
        
        # 数据库大小
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            "event_count": event_count,
            "narrative_count": narrative_count,
            "policy_count": policy_count,
            "user_count": user_count,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "operation_stats": self.stats.copy(),
        }
    
    async def _count_table(self, db, table: str) -> int:
        """计算表行数"""
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
        return (await cursor.fetchone())[0]
    
    async def reset(self) -> None:
        """重置数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memory_events")
            await db.execute("DELETE FROM memory_narratives")
            await db.execute("DELETE FROM memory_policies")
            await db.commit()
        
        # 重置统计
        self.stats = {k: 0 for k in self.stats}
    
    async def close(self) -> None:
        """关闭连接（连接池自动管理，此方法保留）"""
        pass


# 全局实例
_store: Optional[MemorySQLiteStore] = None

def get_memory_store(db_path: Optional[str] = None) -> MemorySQLiteStore:
    """获取全局存储实例"""
    global _store
    if _store is None:
        _store = MemorySQLiteStore(db_path)
    return _store

async def init_memory_store(db_path: Optional[str] = None) -> MemorySQLiteStore:
    """初始化存储"""
    store = get_memory_store(db_path)
    await store.init_db()
    return store
