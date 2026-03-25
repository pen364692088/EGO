"""MVP-10 T20: Commitments Ledger - Track commitments and their status.

Provides commitment tracking with:
- Add, complete, breach operations
- Pending and overdue queries
- Workspace scoring integration
- Cross-run persistence
"""
from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import aiosqlite


class CommitmentStatus(str, Enum):
    """Status of a commitment."""
    PENDING = "pending"
    COMPLETED = "completed"
    BREACHED = "breached"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


@dataclass
class Commitment:
    """A commitment made by the agent.
    
    Attributes:
        id: Unique commitment identifier
        description: What was committed to
        deadline: When it should be completed (Unix timestamp, None = no deadline)
        status: Current status
        created_at: When the commitment was made
        completed_at: When it was completed (if applicable)
        breached_at: When it was breached (if applicable)
        goal_id: Related goal ID (if any)
        priority: Priority level (1-5, default 3)
        context: Additional context about the commitment
        breach_reason: Reason for breach (if breached)
    """
    id: str
    description: str
    deadline: Optional[float] = None
    status: str = CommitmentStatus.PENDING.value
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    breached_at: Optional[float] = None
    goal_id: Optional[str] = None
    priority: int = 3
    context: Dict[str, Any] = field(default_factory=dict)
    breach_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "deadline": self.deadline,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "breached_at": self.breached_at,
            "goal_id": self.goal_id,
            "priority": self.priority,
            "context": self.context,
            "breach_reason": self.breach_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Commitment":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            deadline=data.get("deadline"),
            status=data.get("status", CommitmentStatus.PENDING.value),
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
            breached_at=data.get("breached_at"),
            goal_id=data.get("goal_id"),
            priority=data.get("priority", 3),
            context=data.get("context", {}),
            breach_reason=data.get("breach_reason"),
        )
    
    def is_overdue(self) -> bool:
        """Check if commitment is overdue."""
        if self.deadline is None:
            return False
        if self.status != CommitmentStatus.PENDING.value:
            return False
        return time.time() > self.deadline
    
    def compute_score_weight(self) -> float:
        """Compute weight for workspace scoring.
        
        Pending commitments increase weight based on:
        - Priority (higher priority = more weight)
        - Time remaining (closer to deadline = more weight)
        - Overdue status (overdue = maximum weight)
        """
        if self.status != CommitmentStatus.PENDING.value:
            return 0.0
        
        base_weight = self.priority / 5.0  # 0.2 to 1.0
        
        if self.deadline is None:
            return base_weight * 0.5  # No deadline = lower weight
        
        if self.is_overdue():
            return base_weight * 2.0  # Overdue = double weight
        
        # Time-based weight: closer to deadline = higher weight
        time_remaining = self.deadline - time.time()
        if time_remaining <= 0:
            return base_weight * 2.0
        
        # Scale based on time (1 hour = high urgency, 24 hours = moderate, 7 days = low)
        hours_remaining = time_remaining / 3600.0
        if hours_remaining <= 1:
            urgency = 1.5
        elif hours_remaining <= 24:
            urgency = 1.0 + (24 - hours_remaining) / 24.0 * 0.5
        elif hours_remaining <= 168:  # 7 days
            urgency = 0.5 + (168 - hours_remaining) / 168.0 * 0.5
        else:
            urgency = 0.5
        
        return base_weight * urgency


class CommitmentsLedger:
    """Ledger for tracking commitments.
    
    Features:
    - Add, complete, breach operations
    - Pending and overdue queries
    - Workspace scoring integration
    - Cross-run persistence
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize commitments ledger.
        
        Args:
            db_path: Path to SQLite database. If None, uses default.
        """
        self.db_path = db_path or "./data/emotiond.db"
        self._cache: Dict[str, Commitment] = {}
        self._initialized = False
    
    async def init_db(self) -> None:
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    deadline REAL,
                    status TEXT DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    breached_at REAL,
                    goal_id TEXT,
                    priority INTEGER DEFAULT 3,
                    context TEXT DEFAULT '{}',
                    breach_reason TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_status 
                ON commitments(status)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_deadline 
                ON commitments(deadline)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_goal_id 
                ON commitments(goal_id)
            """)
            await db.commit()
        self._initialized = True
    
    def _generate_id(self, description: str) -> str:
        """Generate unique commitment ID."""
        data = f"{description}:{time.time()}"
        return f"commit_{hashlib.sha256(data.encode()).hexdigest()[:12]}"
    
    async def add(
        self,
        description: str,
        deadline: Optional[float] = None,
        goal_id: Optional[str] = None,
        priority: int = 3,
        context: Optional[Dict[str, Any]] = None,
    ) -> Commitment:
        """Add a new commitment.
        
        Args:
            description: What is being committed to
            deadline: When it should be completed (Unix timestamp)
            goal_id: Related goal ID
            priority: Priority level (1-5)
            context: Additional context
        
        Returns:
            The created Commitment
        """
        if not self._initialized:
            await self.init_db()
        
        commitment_id = self._generate_id(description)
        
        commitment = Commitment(
            id=commitment_id,
            description=description,
            deadline=deadline,
            status=CommitmentStatus.PENDING.value,
            created_at=time.time(),
            goal_id=goal_id,
            priority=min(5, max(1, priority)),
            context=context or {},
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO commitments 
                (id, description, deadline, status, created_at, completed_at, 
                 breached_at, goal_id, priority, context, breach_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                commitment.id,
                commitment.description,
                commitment.deadline,
                commitment.status,
                commitment.created_at,
                commitment.completed_at,
                commitment.breached_at,
                commitment.goal_id,
                commitment.priority,
                json.dumps(commitment.context),
                commitment.breach_reason,
            ))
            await db.commit()
        
        self._cache[commitment_id] = commitment
        return commitment
    
    async def complete(self, commitment_id: str, completed_at: Optional[float] = None) -> Optional[Commitment]:
        """Mark a commitment as completed.
        
        Args:
            commitment_id: The commitment ID
            completed_at: Completion timestamp (defaults to now)
        
        Returns:
            The updated Commitment, or None if not found
        """
        if not self._initialized:
            await self.init_db()
        
        commitment = await self.get(commitment_id)
        if commitment is None:
            return None
        
        if commitment.status != CommitmentStatus.PENDING.value:
            return None  # Already completed or breached
        
        commit_time = completed_at or time.time()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE commitments 
                SET status = ?, completed_at = ?
                WHERE id = ?
            """, (CommitmentStatus.COMPLETED.value, commit_time, commitment_id))
            await db.commit()
        
        commitment.status = CommitmentStatus.COMPLETED.value
        commitment.completed_at = commit_time
        self._cache[commitment_id] = commitment
        
        return commitment
    
    async def breach(
        self, 
        commitment_id: str, 
        reason: Optional[str] = None,
        breached_at: Optional[float] = None,
    ) -> Optional[Commitment]:
        """Mark a commitment as breached.
        
        Args:
            commitment_id: The commitment ID
            reason: Reason for the breach
            breached_at: Breach timestamp (defaults to now)
        
        Returns:
            The updated Commitment, or None if not found
        """
        if not self._initialized:
            await self.init_db()
        
        commitment = await self.get(commitment_id)
        if commitment is None:
            return None
        
        if commitment.status != CommitmentStatus.PENDING.value:
            return None  # Already completed or breached
        
        breach_time = breached_at or time.time()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE commitments 
                SET status = ?, breached_at = ?, breach_reason = ?
                WHERE id = ?
            """, (CommitmentStatus.BREACHED.value, breach_time, reason, commitment_id))
            await db.commit()
        
        commitment.status = CommitmentStatus.BREACHED.value
        commitment.breached_at = breach_time
        commitment.breach_reason = reason
        self._cache[commitment_id] = commitment
        
        return commitment
    
    async def defer(self, commitment_id: str, new_deadline: float) -> Optional[Commitment]:
        """Defer a commitment to a new deadline.
        
        Args:
            commitment_id: The commitment ID
            new_deadline: The new deadline
        
        Returns:
            The updated Commitment, or None if not found
        """
        if not self._initialized:
            await self.init_db()
        
        commitment = await self.get(commitment_id)
        if commitment is None:
            return None
        
        if commitment.status != CommitmentStatus.PENDING.value:
            return None
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE commitments 
                SET deadline = ?, status = ?
                WHERE id = ?
            """, (new_deadline, CommitmentStatus.DEFERRED.value, commitment_id))
            await db.commit()
        
        commitment.deadline = new_deadline
        commitment.status = CommitmentStatus.DEFERRED.value
        self._cache[commitment_id] = commitment
        
        return commitment
    
    async def get(self, commitment_id: str) -> Optional[Commitment]:
        """Get a commitment by ID.
        
        Args:
            commitment_id: The commitment ID
        
        Returns:
            Commitment if found, None otherwise
        """
        if commitment_id in self._cache:
            return self._cache[commitment_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, description, deadline, status, created_at, completed_at,
                       breached_at, goal_id, priority, context, breach_reason
                FROM commitments WHERE id = ?
            """, (commitment_id,))
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            commitment = Commitment(
                id=row[0],
                description=row[1],
                deadline=row[2],
                status=row[3],
                created_at=row[4],
                completed_at=row[5],
                breached_at=row[6],
                goal_id=row[7],
                priority=row[8] or 3,
                context=json.loads(row[9] or "{}"),
                breach_reason=row[10],
            )
            self._cache[commitment_id] = commitment
            return commitment
    
    async def get_pending(self, limit: int = 100) -> List[Commitment]:
        """Get all pending commitments.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of pending Commitments
        """
        if not self._initialized:
            await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, description, deadline, status, created_at, completed_at,
                       breached_at, goal_id, priority, context, breach_reason
                FROM commitments 
                WHERE status = ?
                ORDER BY priority DESC, deadline ASC
                LIMIT ?
            """, (CommitmentStatus.PENDING.value, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_commitment(row) for row in rows]
    
    async def get_overdue(self, limit: int = 100) -> List[Commitment]:
        """Get all overdue commitments.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of overdue Commitments
        """
        if not self._initialized:
            await self.init_db()
        
        now = time.time()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, description, deadline, status, created_at, completed_at,
                       breached_at, goal_id, priority, context, breach_reason
                FROM commitments 
                WHERE status = ? AND deadline IS NOT NULL AND deadline < ?
                ORDER BY deadline ASC
                LIMIT ?
            """, (CommitmentStatus.PENDING.value, now, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_commitment(row) for row in rows]
    
    async def get_by_goal(self, goal_id: str) -> List[Commitment]:
        """Get commitments related to a goal.
        
        Args:
            goal_id: The goal ID
        
        Returns:
            List of related Commitments
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, description, deadline, status, created_at, completed_at,
                       breached_at, goal_id, priority, context, breach_reason
                FROM commitments 
                WHERE goal_id = ?
                ORDER BY created_at DESC
            """, (goal_id,))
            rows = await cursor.fetchall()
        
        return [self._row_to_commitment(row) for row in rows]
    
    async def compute_workspace_score_weight(self) -> float:
        """Compute total weight for workspace scoring.
        
        Sums the score weights of all pending commitments.
        
        Returns:
            Total weight (used to affect workspace scoring)
        """
        pending = await self.get_pending()
        return sum(c.compute_score_weight() for c in pending)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get commitment statistics.
        
        Returns:
            Dictionary with statistics
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Count by status
            cursor = await db.execute("""
                SELECT status, COUNT(*) as cnt 
                FROM commitments 
                GROUP BY status
            """)
            by_status = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Overdue count
            now = time.time()
            cursor = await db.execute("""
                SELECT COUNT(*) FROM commitments 
                WHERE status = ? AND deadline IS NOT NULL AND deadline < ?
            """, (CommitmentStatus.PENDING.value, now))
            overdue = (await cursor.fetchone())[0]
            
            # Average completion time
            cursor = await db.execute("""
                SELECT AVG(completed_at - created_at) 
                FROM commitments 
                WHERE status = ? AND completed_at IS NOT NULL
            """, (CommitmentStatus.COMPLETED.value,))
            avg_completion = (await cursor.fetchone())[0]
            
            # Breach rate
            cursor = await db.execute("SELECT COUNT(*) FROM commitments")
            total_row = await cursor.fetchone()
            total = total_row[0] if total_row else 0
            breached = by_status.get(CommitmentStatus.BREACHED.value, 0)
        
        return {
            "total": total,
            "by_status": by_status,
            "overdue": overdue,
            "avg_completion_time_seconds": avg_completion,
            "breach_rate": breached / total if total > 0 else 0.0,
            "workspace_weight": await self.compute_workspace_score_weight(),
        }
    
    async def check_overdue_and_breach(self) -> List[Commitment]:
        """Check for overdue commitments and mark them as breached.
        
        This can be called periodically to auto-breach overdue commitments.
        
        Returns:
            List of newly breached commitments
        """
        overdue = await self.get_overdue()
        breached = []
        
        for commitment in overdue:
            result = await self.breach(
                commitment.id, 
                reason="Auto-breached: deadline passed"
            )
            if result:
                breached.append(result)
        
        return breached
    
    async def clear(self) -> None:
        """Clear all commitments (for testing)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM commitments")
            await db.commit()
        self._cache.clear()
    
    async def export_for_persistence(self) -> List[Dict[str, Any]]:
        """Export all commitments for cross-run persistence.
        
        Returns:
            List of commitment dictionaries
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, description, deadline, status, created_at, completed_at,
                       breached_at, goal_id, priority, context, breach_reason
                FROM commitments
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
        
        return [self._row_to_commitment(row).to_dict() for row in rows]
    
    async def import_from_persistence(self, commitments: List[Dict[str, Any]]) -> int:
        """Import commitments from persistence.
        
        Args:
            commitments: List of commitment dictionaries
        
        Returns:
            Number of commitments imported
        """
        if not self._initialized:
            await self.init_db()
        
        count = 0
        for data in commitments:
            commitment = Commitment.from_dict(data)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO commitments 
                    (id, description, deadline, status, created_at, completed_at,
                     breached_at, goal_id, priority, context, breach_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    commitment.id,
                    commitment.description,
                    commitment.deadline,
                    commitment.status,
                    commitment.created_at,
                    commitment.completed_at,
                    commitment.breached_at,
                    commitment.goal_id,
                    commitment.priority,
                    json.dumps(commitment.context),
                    commitment.breach_reason,
                ))
                await db.commit()
            
            self._cache[commitment.id] = commitment
            count += 1
        
        return count
    
    def _row_to_commitment(self, row) -> Commitment:
        """Convert database row to Commitment."""
        return Commitment(
            id=row[0],
            description=row[1],
            deadline=row[2],
            status=row[3],
            created_at=row[4],
            completed_at=row[5],
            breached_at=row[6],
            goal_id=row[7],
            priority=row[8] or 3,
            context=json.loads(row[9] or "{}"),
            breach_reason=row[10],
        )


# Global instance
_commitments_ledger: Optional[CommitmentsLedger] = None


def get_commitments_ledger(db_path: Optional[str] = None) -> CommitmentsLedger:
    """Get or create the global commitments ledger instance."""
    global _commitments_ledger
    if _commitments_ledger is None:
        _commitments_ledger = CommitmentsLedger(db_path)
    return _commitments_ledger
