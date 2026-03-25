"""MVP-10 T19: Narrative Memory - Versioned narrative entries with evidence tracking.

Provides narrative memory with:
- Versioned narrative entries
- Evidence pointers to episodic events
- Correction mechanisms with audit trail
- Contradiction detection with facts
"""
from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import aiosqlite


class NarrativeStatus(str, Enum):
    """Status of a narrative entry."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CORRECTED = "corrected"
    RETRACTED = "retracted"


@dataclass
class NarrativeEntry:
    """A versioned narrative entry with evidence pointers.
    
    Attributes:
        version: Version number (monotonically increasing)
        content: The narrative content text
        evidence_pointers: List of episodic event IDs supporting this narrative
        timestamp: When this entry was created
        entry_id: Unique identifier for this entry
        previous_version_id: ID of the previous version (if any)
        status: Current status of the entry
        correction_reason: Reason for correction (if corrected)
        metadata: Additional metadata
    """
    version: int
    content: str
    evidence_pointers: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    entry_id: str = field(default="")
    previous_version_id: Optional[str] = None
    status: str = NarrativeStatus.ACTIVE.value
    correction_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique entry ID."""
        data = f"{self.version}:{self.content[:50]}:{self.timestamp}"
        return f"narr_{hashlib.sha256(data.encode()).hexdigest()[:12]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "version": self.version,
            "content": self.content,
            "evidence_pointers": self.evidence_pointers,
            "timestamp": self.timestamp,
            "previous_version_id": self.previous_version_id,
            "status": self.status,
            "correction_reason": self.correction_reason,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NarrativeEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data.get("entry_id", ""),
            version=data["version"],
            content=data["content"],
            evidence_pointers=data.get("evidence_pointers", []),
            timestamp=data.get("timestamp", time.time()),
            previous_version_id=data.get("previous_version_id"),
            status=data.get("status", NarrativeStatus.ACTIVE.value),
            correction_reason=data.get("correction_reason"),
            metadata=data.get("metadata", {}),
        )
    
    def compute_hash(self) -> str:
        """Compute hash for integrity checking."""
        data = f"{self.version}:{self.content}:{':'.join(sorted(self.evidence_pointers))}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class Fact:
    """A fact that narratives should not contradict."""
    fact_id: str
    content: str
    source: str  # Where the fact came from
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fact":
        return cls(
            fact_id=data["fact_id"],
            content=data["content"],
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", time.time()),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class Contradiction:
    """Record of a detected contradiction."""
    entry_id: str
    fact_id: str
    entry_content: str
    fact_content: str
    contradiction_type: str  # "direct", "implied", "contextual"
    severity: float  # 0.0-1.0
    detected_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "fact_id": self.fact_id,
            "entry_content": self.entry_content,
            "fact_content": self.fact_content,
            "contradiction_type": self.contradiction_type,
            "severity": self.severity,
            "detected_at": self.detected_at,
        }


class NarrativeMemory:
    """Narrative memory with versioning and evidence tracking.
    
    Features:
    - Versioned narrative entries
    - Evidence pointers to episodic events
    - Correction with audit trail
    - Contradiction detection with facts
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize narrative memory.
        
        Args:
            db_path: Path to SQLite database. If None, uses default.
        """
        self.db_path = db_path or "./data/emotiond.db"
        self._entry_cache: Dict[str, NarrativeEntry] = {}
        self._fact_cache: Dict[str, Fact] = {}
        self._initialized = False
    
    async def init_db(self) -> None:
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Narrative entries table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS narrative_entries (
                    entry_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    evidence_pointers TEXT DEFAULT '[]',
                    timestamp REAL NOT NULL,
                    previous_version_id TEXT,
                    status TEXT DEFAULT 'active',
                    correction_reason TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_narrative_version 
                ON narrative_entries(version)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_narrative_status 
                ON narrative_entries(status)
            """)
            
            # Facts table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS narrative_facts (
                    fact_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'unknown',
                    timestamp REAL NOT NULL,
                    confidence REAL DEFAULT 1.0
                )
            """)
            
            # Contradictions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS narrative_contradictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT NOT NULL,
                    fact_id TEXT NOT NULL,
                    entry_content TEXT NOT NULL,
                    fact_content TEXT NOT NULL,
                    contradiction_type TEXT NOT NULL,
                    severity REAL NOT NULL,
                    detected_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_contradiction_entry 
                ON narrative_contradictions(entry_id)
            """)
            
            await db.commit()
        self._initialized = True
    
    async def add_entry(
        self,
        content: str,
        evidence_pointers: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NarrativeEntry:
        """Add a new narrative entry.
        
        Args:
            content: The narrative content
            evidence_pointers: List of episodic event IDs as evidence
            metadata: Additional metadata
        
        Returns:
            The created NarrativeEntry
        """
        if not self._initialized:
            await self.init_db()
        
        # Get current max version
        current_version = await self._get_max_version()
        new_version = current_version + 1
        
        entry = NarrativeEntry(
            version=new_version,
            content=content,
            evidence_pointers=evidence_pointers or [],
            timestamp=time.time(),
            metadata=metadata or {},
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO narrative_entries 
                (entry_id, version, content, evidence_pointers, timestamp, 
                 previous_version_id, status, correction_reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.version,
                entry.content,
                json.dumps(entry.evidence_pointers),
                entry.timestamp,
                entry.previous_version_id,
                entry.status,
                entry.correction_reason,
                json.dumps(entry.metadata),
            ))
            await db.commit()
        
        self._entry_cache[entry.entry_id] = entry
        
        # Check for contradictions with existing facts
        await self._check_contradictions(entry)
        
        return entry
    
    async def correct_entry(
        self,
        entry_id: str,
        new_content: str,
        new_evidence_pointers: Optional[List[str]] = None,
        reason: str = "correction",
    ) -> NarrativeEntry:
        """Correct an existing narrative entry.
        
        Creates a new version with the correction and marks the old entry as corrected.
        
        Args:
            entry_id: ID of the entry to correct
            new_content: The corrected content
            new_evidence_pointers: New evidence pointers (if changed)
            reason: Reason for the correction
        
        Returns:
            The new corrected NarrativeEntry
        """
        if not self._initialized:
            await self.init_db()
        
        # Get the old entry
        old_entry = await self.get_entry(entry_id)
        if old_entry is None:
            raise ValueError(f"Entry {entry_id} not found")
        
        # Mark old entry as corrected
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE narrative_entries 
                SET status = ?, correction_reason = ?
                WHERE entry_id = ?
            """, (NarrativeStatus.CORRECTED.value, reason, entry_id))
            await db.commit()
        
        # Update cache
        if entry_id in self._entry_cache:
            self._entry_cache[entry_id].status = NarrativeStatus.CORRECTED.value
            self._entry_cache[entry_id].correction_reason = reason
        
        # Create new entry with incremented version
        new_version = await self._get_max_version() + 1
        
        new_entry = NarrativeEntry(
            version=new_version,
            content=new_content,
            evidence_pointers=new_evidence_pointers or old_entry.evidence_pointers,
            timestamp=time.time(),
            previous_version_id=entry_id,
            status=NarrativeStatus.ACTIVE.value,
            metadata={"correction_of": entry_id, "reason": reason},
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO narrative_entries 
                (entry_id, version, content, evidence_pointers, timestamp, 
                 previous_version_id, status, correction_reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_entry.entry_id,
                new_entry.version,
                new_entry.content,
                json.dumps(new_entry.evidence_pointers),
                new_entry.timestamp,
                new_entry.previous_version_id,
                new_entry.status,
                new_entry.correction_reason,
                json.dumps(new_entry.metadata),
            ))
            await db.commit()
        
        self._entry_cache[new_entry.entry_id] = new_entry
        return new_entry
    
    async def get_entry(self, entry_id: str) -> Optional[NarrativeEntry]:
        """Get a narrative entry by ID.
        
        Args:
            entry_id: The entry ID
        
        Returns:
            NarrativeEntry if found, None otherwise
        """
        if entry_id in self._entry_cache:
            return self._entry_cache[entry_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT entry_id, version, content, evidence_pointers, timestamp,
                       previous_version_id, status, correction_reason, metadata
                FROM narrative_entries WHERE entry_id = ?
            """, (entry_id,))
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            entry = NarrativeEntry(
                entry_id=row[0],
                version=row[1],
                content=row[2],
                evidence_pointers=json.loads(row[3] or "[]"),
                timestamp=row[4],
                previous_version_id=row[5],
                status=row[6],
                correction_reason=row[7],
                metadata=json.loads(row[8] or "{}"),
            )
            self._entry_cache[entry_id] = entry
            return entry
    
    async def get_active_entries(self, limit: int = 100) -> List[NarrativeEntry]:
        """Get all active narrative entries.
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of active NarrativeEntry objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT entry_id, version, content, evidence_pointers, timestamp,
                       previous_version_id, status, correction_reason, metadata
                FROM narrative_entries 
                WHERE status = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (NarrativeStatus.ACTIVE.value, limit))
            rows = await cursor.fetchall()
        
        return [self._row_to_entry(row) for row in rows]
    
    async def get_version_history(self, entry_id: str) -> List[NarrativeEntry]:
        """Get the version history for an entry.
        
        Follows previous_version_id links to build the history.
        
        Args:
            entry_id: The entry ID to get history for
        
        Returns:
            List of entries in the history (ordered newest to oldest)
        """
        history = []
        visited = set()
        current_id = entry_id
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            entry = await self.get_entry(current_id)
            if entry:
                history.append(entry)
                current_id = entry.previous_version_id
            else:
                break
        
        return history
    
    async def verify_consistency(self) -> Dict[str, Any]:
        """Verify consistency of narrative entries.
        
        Checks:
        - All evidence pointers reference valid events
        - No orphaned previous_version_id references
        - Version numbers are consistent
        
        Returns:
            Dictionary with consistency check results
        """
        issues = []
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check for entries with missing previous_version_id references
            cursor = await db.execute("""
                SELECT n1.entry_id, n1.previous_version_id
                FROM narrative_entries n1
                WHERE n1.previous_version_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM narrative_entries n2 
                    WHERE n2.entry_id = n1.previous_version_id
                )
            """)
            orphaned = await cursor.fetchall()
            for row in orphaned:
                issues.append({
                    "type": "orphaned_reference",
                    "entry_id": row[0],
                    "missing_previous_id": row[1],
                })
            
            # Check for version consistency
            cursor = await db.execute("""
                SELECT entry_id, version, previous_version_id
                FROM narrative_entries
                WHERE previous_version_id IS NOT NULL
            """)
            entries = await cursor.fetchall()
            
            for entry_id, version, prev_id in entries:
                prev_entry = await self.get_entry(prev_id)
                if prev_entry and prev_entry.version >= version:
                    issues.append({
                        "type": "version_inconsistency",
                        "entry_id": entry_id,
                        "version": version,
                        "previous_version": prev_entry.version,
                    })
        
        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "total_checked": len(self._entry_cache),
        }
    
    async def add_fact(
        self,
        fact_id: str,
        content: str,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> Fact:
        """Add a fact for contradiction checking.
        
        Args:
            fact_id: Unique fact identifier
            content: The fact content
            source: Source of the fact
            confidence: Confidence level (0.0-1.0)
        
        Returns:
            The created Fact
        """
        if not self._initialized:
            await self.init_db()
        
        fact = Fact(
            fact_id=fact_id,
            content=content,
            source=source,
            timestamp=time.time(),
            confidence=confidence,
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO narrative_facts 
                (fact_id, content, source, timestamp, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (fact.fact_id, fact.content, fact.source, fact.timestamp, fact.confidence))
            await db.commit()
        
        self._fact_cache[fact_id] = fact
        
        # Check existing entries for contradictions with new fact
        await self._check_entries_against_fact(fact)
        
        return fact
    
    async def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Get a fact by ID."""
        if fact_id in self._fact_cache:
            return self._fact_cache[fact_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT fact_id, content, source, timestamp, confidence
                FROM narrative_facts WHERE fact_id = ?
            """, (fact_id,))
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            fact = Fact(
                fact_id=row[0],
                content=row[1],
                source=row[2],
                timestamp=row[3],
                confidence=row[4],
            )
            self._fact_cache[fact_id] = fact
            return fact
    
    async def get_contradictions(self, entry_id: Optional[str] = None) -> List[Contradiction]:
        """Get detected contradictions.
        
        Args:
            entry_id: If provided, get contradictions for this entry only
        
        Returns:
            List of Contradiction objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            if entry_id:
                cursor = await db.execute("""
                    SELECT entry_id, fact_id, entry_content, fact_content,
                           contradiction_type, severity, detected_at
                    FROM narrative_contradictions WHERE entry_id = ?
                    ORDER BY detected_at DESC
                """, (entry_id,))
            else:
                cursor = await db.execute("""
                    SELECT entry_id, fact_id, entry_content, fact_content,
                           contradiction_type, severity, detected_at
                    FROM narrative_contradictions
                    ORDER BY detected_at DESC
                """)
            rows = await cursor.fetchall()
        
        return [Contradiction(
            entry_id=row[0],
            fact_id=row[1],
            entry_content=row[2],
            fact_content=row[3],
            contradiction_type=row[4],
            severity=row[5],
            detected_at=row[6],
        ) for row in rows]
    
    async def _check_contradictions(self, entry: NarrativeEntry) -> List[Contradiction]:
        """Check entry for contradictions with facts.
        
        Args:
            entry: The entry to check
        
        Returns:
            List of detected Contradictions
        """
        contradictions = []
        
        # Get all facts
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT fact_id, content FROM narrative_facts")
            facts = await cursor.fetchall()
        
        entry_lower = entry.content.lower()
        
        for fact_id, fact_content in facts:
            fact_lower = fact_content.lower()
            
            # Simple contradiction detection
            contradiction = self._detect_contradiction(entry_lower, fact_lower, fact_id)
            if contradiction:
                contradictions.append(contradiction)
                
                # Store contradiction
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT INTO narrative_contradictions 
                        (entry_id, fact_id, entry_content, fact_content, 
                         contradiction_type, severity, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.entry_id,
                        fact_id,
                        entry.content[:200],
                        fact_content[:200],
                        contradiction.contradiction_type,
                        contradiction.severity,
                        time.time(),
                    ))
                    await db.commit()
        
        return contradictions
    
    def _detect_contradiction(
        self, 
        entry_content: str, 
        fact_content: str, 
        fact_id: str,
    ) -> Optional[Contradiction]:
        """Detect contradiction between entry and fact.
        
        Uses simple heuristics for contradiction detection.
        
        Args:
            entry_content: Entry content (lowercase)
            fact_content: Fact content (lowercase)
            fact_id: The fact ID
        
        Returns:
            Contradiction if detected, None otherwise
        """
        # Direct negation patterns
        negation_patterns = [
            (" not ", " "),
            (" never ", " "),
            (" no ", " "),
            (" isn't ", " is "),
            (" doesn't ", " does "),
            (" won't ", " will "),
            (" can't ", " can "),
            (" cannot ", " can "),
        ]
        
        for neg, pos in negation_patterns:
            if neg in entry_content:
                # Check if fact contains the positive form
                positive_entry = entry_content.replace(neg, pos)
                if fact_content in positive_entry or positive_entry in fact_content:
                    return Contradiction(
                        entry_id="",  # Will be set by caller
                        fact_id=fact_id,
                        entry_content=entry_content[:200],
                        fact_content=fact_content[:200],
                        contradiction_type="direct",
                        severity=0.8,
                    )
        
        # Check for explicit contradiction markers
        contradiction_markers = ["but", "however", "actually", "in fact", "contrary to"]
        for marker in contradiction_markers:
            if marker in entry_content and fact_content[:30] in entry_content:
                return Contradiction(
                    entry_id="",
                    fact_id=fact_id,
                    entry_content=entry_content[:200],
                    fact_content=fact_content[:200],
                    contradiction_type="implied",
                    severity=0.6,
                )
        
        return None
    
    async def _check_entries_against_fact(self, fact: Fact) -> None:
        """Check all active entries against a new fact."""
        entries = await self.get_active_entries()
        for entry in entries:
            await self._check_contradictions(entry)
    
    async def _get_max_version(self) -> int:
        """Get the current maximum version number."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT MAX(version) FROM narrative_entries")
            row = await cursor.fetchone()
            return int(row[0] or 0)
    
    async def clear(self) -> None:
        """Clear all narrative data (for testing)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM narrative_entries")
            await db.execute("DELETE FROM narrative_facts")
            await db.execute("DELETE FROM narrative_contradictions")
            await db.commit()
        self._entry_cache.clear()
        self._fact_cache.clear()
    
    def _row_to_entry(self, row) -> NarrativeEntry:
        """Convert database row to NarrativeEntry."""
        return NarrativeEntry(
            entry_id=row[0],
            version=row[1],
            content=row[2],
            evidence_pointers=json.loads(row[3] or "[]"),
            timestamp=row[4],
            previous_version_id=row[5],
            status=row[6],
            correction_reason=row[7],
            metadata=json.loads(row[8] or "{}"),
        )


# Global instance
_narrative_memory: Optional[NarrativeMemory] = None


def get_narrative_memory(db_path: Optional[str] = None) -> NarrativeMemory:
    """Get or create the global narrative memory instance."""
    global _narrative_memory
    if _narrative_memory is None:
        _narrative_memory = NarrativeMemory(db_path)
    return _narrative_memory
