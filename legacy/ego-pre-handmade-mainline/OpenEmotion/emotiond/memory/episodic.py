"""MVP-10 T18: Episodic Memory - Event storage and retrieval for goal tracking.

Provides episodic event storage with:
- Query by goal_id, failure_type, time_range
- Integration with ledger for event chain logging
- Deterministic retrieval for replay scenarios
"""
from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import aiosqlite


class EventType(str, Enum):
    """Types of episodic events."""
    GOAL_SET = "goal_set"
    GOAL_PROGRESS = "goal_progress"
    GOAL_ACHIEVED = "goal_achieved"
    GOAL_FAILED = "goal_failed"
    ACTION_TAKEN = "action_taken"
    DECISION_MADE = "decision_made"
    FAILURE_OCCURRED = "failure_occurred"
    INTERACTION = "interaction"
    STATE_CHANGE = "state_change"


class FailureType(str, Enum):
    """Types of failures that can occur."""
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    CONSTRAINT_VIOLATION = "constraint_violation"
    EXTERNAL_FAILURE = "external_failure"
    USER_ABORT = "user_abort"
    UNKNOWN = "unknown"


@dataclass
class EpisodicEvent:
    """A single episodic event with full context.
    
    Attributes:
        event_id: Unique identifier for this event
        timestamp: Unix timestamp when event occurred
        event_type: Type of event (goal_set, action_taken, etc.)
        context: Additional context data (actor, target, metadata)
        outcome: Result of the event (success, failure, partial)
        goal_id: ID of the goal this event relates to (if any)
        parent_event_id: ID of the parent event for event chains
        failure_type: Type of failure if outcome is failure
        evidence: Supporting evidence for this event
        tags: Tags for categorization and search
    """
    event_id: str
    timestamp: float
    event_type: str
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: str = "neutral"  # success, failure, partial, neutral
    goal_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    failure_type: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "context": self.context,
            "outcome": self.outcome,
            "goal_id": self.goal_id,
            "parent_event_id": self.parent_event_id,
            "failure_type": self.failure_type,
            "evidence": self.evidence,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicEvent":
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            event_type=data["event_type"],
            context=data.get("context", {}),
            outcome=data.get("outcome", "neutral"),
            goal_id=data.get("goal_id"),
            parent_event_id=data.get("parent_event_id"),
            failure_type=data.get("failure_type"),
            evidence=data.get("evidence", {}),
            tags=data.get("tags", []),
        )
    
    def compute_hash(self) -> str:
        """Compute deterministic hash for this event."""
        data = f"{self.event_id}:{self.timestamp}:{self.event_type}:{self.outcome}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class EpisodicMemory:
    """Episodic memory for storing and retrieving events.
    
    Provides:
    - Event storage with automatic indexing
    - Query by goal_id, failure_type, time_range
    - Event chain retrieval for replay
    - Integration with ledger for event chain logging
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize episodic memory.
        
        Args:
            db_path: Path to SQLite database. If None, uses default.
        """
        self.db_path = db_path or "./data/emotiond.db"
        self._cache: Dict[str, EpisodicEvent] = {}
        self._initialized = False
    
    async def init_db(self) -> None:
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodic_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    outcome TEXT DEFAULT 'neutral',
                    goal_id TEXT,
                    parent_event_id TEXT,
                    failure_type TEXT,
                    evidence TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]',
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_goal_id 
                ON episodic_events(goal_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_failure_type 
                ON episodic_events(failure_type)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_timestamp 
                ON episodic_events(timestamp)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodic_event_type 
                ON episodic_events(event_type)
            """)
            await db.commit()
        self._initialized = True
    
    def _generate_event_id(self, event_type: str, timestamp: float) -> str:
        """Generate a unique event ID."""
        data = f"{event_type}:{timestamp}:{time.time()}"
        return f"evt_{hashlib.sha256(data.encode()).hexdigest()[:12]}"
    
    async def store(
        self,
        event_type: str,
        context: Dict[str, Any],
        outcome: str = "neutral",
        goal_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        failure_type: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        timestamp: Optional[float] = None,
    ) -> EpisodicEvent:
        """Store a new episodic event.
        
        Args:
            event_type: Type of event
            context: Event context data
            outcome: Event outcome (success, failure, partial, neutral)
            goal_id: Related goal ID
            parent_event_id: Parent event for chains
            failure_type: Type of failure if applicable
            evidence: Supporting evidence
            tags: Categorization tags
            timestamp: Event timestamp (defaults to now)
        
        Returns:
            The created EpisodicEvent
        """
        if not self._initialized:
            await self.init_db()
        
        ts = timestamp or time.time()
        event_id = self._generate_event_id(event_type, ts)
        
        event = EpisodicEvent(
            event_id=event_id,
            timestamp=ts,
            event_type=event_type,
            context=context,
            outcome=outcome,
            goal_id=goal_id,
            parent_event_id=parent_event_id,
            failure_type=failure_type,
            evidence=evidence or {},
            tags=tags or [],
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO episodic_events 
                (event_id, timestamp, event_type, context, outcome, goal_id, 
                 parent_event_id, failure_type, evidence, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.timestamp,
                event.event_type,
                json.dumps(event.context),
                event.outcome,
                event.goal_id,
                event.parent_event_id,
                event.failure_type,
                json.dumps(event.evidence),
                json.dumps(event.tags),
            ))
            await db.commit()
        
        self._cache[event_id] = event
        return event
    
    async def retrieve(self, event_id: str) -> Optional[EpisodicEvent]:
        """Retrieve an event by ID.
        
        Args:
            event_id: The event ID to retrieve
        
        Returns:
            EpisodicEvent if found, None otherwise
        """
        if event_id in self._cache:
            return self._cache[event_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                       parent_event_id, failure_type, evidence, tags
                FROM episodic_events WHERE event_id = ?
            """, (event_id,))
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            event = EpisodicEvent(
                event_id=row[0],
                timestamp=row[1],
                event_type=row[2],
                context=json.loads(row[3] or "{}"),
                outcome=row[4],
                goal_id=row[5],
                parent_event_id=row[6],
                failure_type=row[7],
                evidence=json.loads(row[8] or "{}"),
                tags=json.loads(row[9] or "[]"),
            )
            self._cache[event_id] = event
            return event
    
    async def query_by_goal_id(
        self, 
        goal_id: str, 
        limit: int = 100,
        order_desc: bool = True,
    ) -> List[EpisodicEvent]:
        """Query events by goal ID.
        
        Args:
            goal_id: The goal ID to filter by
            limit: Maximum number of events to return
            order_desc: Order by timestamp descending if True
        
        Returns:
            List of matching EpisodicEvents
        """
        order = "DESC" if order_desc else "ASC"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                       parent_event_id, failure_type, evidence, tags
                FROM episodic_events 
                WHERE goal_id = ?
                ORDER BY timestamp {order}
                LIMIT ?
            """, (goal_id, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    async def query_by_failure_type(
        self,
        failure_type: str,
        limit: int = 100,
        order_desc: bool = True,
    ) -> List[EpisodicEvent]:
        """Query events by failure type.
        
        Args:
            failure_type: The failure type to filter by
            limit: Maximum number of events to return
            order_desc: Order by timestamp descending if True
        
        Returns:
            List of matching EpisodicEvents
        """
        order = "DESC" if order_desc else "ASC"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                       parent_event_id, failure_type, evidence, tags
                FROM episodic_events 
                WHERE failure_type = ?
                ORDER BY timestamp {order}
                LIMIT ?
            """, (failure_type, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    async def query_by_time_range(
        self,
        start_time: float,
        end_time: float,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[EpisodicEvent]:
        """Query events by time range.
        
        Args:
            start_time: Start of time range (Unix timestamp)
            end_time: End of time range (Unix timestamp)
            event_type: Optional event type filter
            limit: Maximum number of events to return
        
        Returns:
            List of matching EpisodicEvents
        """
        async with aiosqlite.connect(self.db_path) as db:
            if event_type:
                cursor = await db.execute("""
                    SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                           parent_event_id, failure_type, evidence, tags
                    FROM episodic_events 
                    WHERE timestamp >= ? AND timestamp <= ? AND event_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (start_time, end_time, event_type, limit))
            else:
                cursor = await db.execute("""
                    SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                           parent_event_id, failure_type, evidence, tags
                    FROM episodic_events 
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (start_time, end_time, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    async def get_event_chain(self, event_id: str) -> List[EpisodicEvent]:
        """Get the full chain of events leading to/from an event.
        
        Follows parent_event_id links to build the chain.
        
        Args:
            event_id: The event ID to start from
        
        Returns:
            List of events in the chain (ordered from root to leaf)
        """
        chain = []
        visited = set()
        current_id = event_id
        
        # First, find the root by following parent links up
        ancestors = []
        current = await self.retrieve(current_id)
        while current and current.event_id not in visited:
            visited.add(current.event_id)
            ancestors.append(current)
            if current.parent_event_id:
                current = await self.retrieve(current.parent_event_id)
            else:
                break
        
        # Reverse to get root-to-leaf order
        chain = list(reversed(ancestors))
        
        return chain
    
    async def get_children(self, event_id: str) -> List[EpisodicEvent]:
        """Get all events that have this event as parent.
        
        Args:
            event_id: The parent event ID
        
        Returns:
            List of child events
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT event_id, timestamp, event_type, context, outcome, goal_id,
                       parent_event_id, failure_type, evidence, tags
                FROM episodic_events 
                WHERE parent_event_id = ?
                ORDER BY timestamp ASC
            """, (event_id,))
            rows = await cursor.fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    async def log_to_ledger(
        self,
        event: EpisodicEvent,
        ledger_path: Optional[str] = None,
    ) -> str:
        """Log event to ledger for event chain logging.
        
        Args:
            event: The event to log
            ledger_path: Optional custom ledger path
        
        Returns:
            Ledger entry ID
        """
        ledger = ledger_path or f"./data/episodic_ledger.jsonl"
        entry = {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "outcome": event.outcome,
            "goal_id": event.goal_id,
            "parent_event_id": event.parent_event_id,
            "hash": event.compute_hash(),
            "logged_at": time.time(),
        }
        
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(ledger) if os.path.dirname(ledger) else ".", exist_ok=True)
        
        with open(ledger, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        return event.event_id
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored events.
        
        Returns:
            Dictionary with event statistics
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Total count
            cursor = await db.execute("SELECT COUNT(*) FROM episodic_events")
            total = (await cursor.fetchone())[0]
            
            # Count by event_type
            cursor = await db.execute("""
                SELECT event_type, COUNT(*) as cnt 
                FROM episodic_events 
                GROUP BY event_type
            """)
            by_type = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Count by outcome
            cursor = await db.execute("""
                SELECT outcome, COUNT(*) as cnt 
                FROM episodic_events 
                GROUP BY outcome
            """)
            by_outcome = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Failure count
            cursor = await db.execute("""
                SELECT COUNT(*) FROM episodic_events WHERE failure_type IS NOT NULL
            """)
            failures = (await cursor.fetchone())[0]
        
        return {
            "total_events": total,
            "by_type": by_type,
            "by_outcome": by_outcome,
            "total_failures": failures,
        }
    
    async def clear(self) -> None:
        """Clear all episodic events (for testing)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM episodic_events")
            await db.commit()
        self._cache.clear()
    
    def _row_to_event(self, row: Tuple) -> EpisodicEvent:
        """Convert a database row to EpisodicEvent."""
        return EpisodicEvent(
            event_id=row[0],
            timestamp=row[1],
            event_type=row[2],
            context=json.loads(row[3] or "{}"),
            outcome=row[4],
            goal_id=row[5],
            parent_event_id=row[6],
            failure_type=row[7],
            evidence=json.loads(row[8] or "{}"),
            tags=json.loads(row[9] or "[]"),
        )


# Global instance for convenience
_episodic_memory: Optional[EpisodicMemory] = None


def get_episodic_memory(db_path: Optional[str] = None) -> EpisodicMemory:
    """Get or create the global episodic memory instance."""
    global _episodic_memory
    if _episodic_memory is None:
        _episodic_memory = EpisodicMemory(db_path)
    return _episodic_memory
