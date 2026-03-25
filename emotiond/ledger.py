"""
D4: Promise/Contract Ledger for Betrayal Detection

Provides evidence-driven betrayal detection by tracking promises made between parties.
A betrayal is only triggered when there's an active promise that was violated.

Core principle: Betrayal requires evidence (promise + violation), not just semantic classification.
"""
import json
import time
import re
import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import aiosqlite


class Promise(BaseModel):
    """A promise/contract between two parties."""
    promise_id: str = Field(description="Unique identifier for this promise")
    promiser: str = Field(description="Who made the promise")
    promisee: str = Field(description="Who received the promise")
    content: str = Field(description="What was promised")
    created_at: float = Field(description="Timestamp when promise was made")
    deadline: Optional[float] = Field(default=None, description="When it should be fulfilled")
    conditions: List[str] = Field(default_factory=list, description="Conditions for fulfillment")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="How certain we are this is a real promise")
    evidence: str = Field(description="The text that indicated the promise")
    status: str = Field(default="active", description="active, fulfilled, broken, deferred")
    fulfilled_at: Optional[float] = Field(default=None, description="When promise was fulfilled")
    broken_at: Optional[float] = Field(default=None, description="When promise was broken")
    broken_evidence: Optional[str] = Field(default=None, description="Evidence of why promise was broken")


class ViolationResult(BaseModel):
    """Result of a violation detection."""
    promise: Promise
    violation_type: str  # "timeout", "contradiction", "behavioral"
    evidence: str
    severity: float  # 0.0-1.0
    timestamp: float


# Promise detection patterns (rule-based, not ML)
PROMISE_PATTERNS = {
    # Chinese patterns
    r"我保证(.+)": {"lang": "zh", "confidence": 0.9},
    r"我承诺(.+)": {"lang": "zh", "confidence": 0.95},
    r"我一定(.+)": {"lang": "zh", "confidence": 0.7},
    r"我会(.+)": {"lang": "zh", "confidence": 0.6},
    r"答应你(.+)": {"lang": "zh", "confidence": 0.8},
    r"放心[，,]?(.+)": {"lang": "zh", "confidence": 0.6},
    r"我发誓(.+)": {"lang": "zh", "confidence": 0.85},
    r"说好了(.+)": {"lang": "zh", "confidence": 0.7},
    
    # English patterns
    r"i\s+promise\s+(.+)": {"lang": "en", "confidence": 0.9},
    r"i\s+will\s+(.+)": {"lang": "en", "confidence": 0.6},
    r"i\s+swear\s+(.+)": {"lang": "en", "confidence": 0.85},
    r"i\s+guarantee\s+(.+)": {"lang": "en", "confidence": 0.85},
    r"i\s+commit\s+to\s+(.+)": {"lang": "en", "confidence": 0.9},
    r"i'll\s+make\s+sure\s+(.+)": {"lang": "en", "confidence": 0.7},
    r"you\s+have\s+my\s+word\s+(.+)": {"lang": "en", "confidence": 0.85},
    r"count\s+on\s+me\s+to\s+(.+)": {"lang": "en", "confidence": 0.75},
}

# Violation detection patterns
VIOLATION_PATTERNS = {
    # Chinese contradiction patterns
    r"算了[，,]?不用了": {"type": "contradiction", "severity": 0.7},
    r"我不[能会]": {"type": "contradiction", "severity": 0.8},
    r"做不到": {"type": "contradiction", "severity": 0.8},
    r"没时间": {"type": "behavioral", "severity": 0.5},
    r"忘记了": {"type": "behavioral", "severity": 0.6},
    r"不好意思[，,]?我": {"type": "behavioral", "severity": 0.4},
    
    # English contradiction patterns
    r"i\s+can'?t": {"type": "contradiction", "severity": 0.8},
    r"i\s+won'?t": {"type": "contradiction", "severity": 0.85},
    r"sorry,?\s+i\s+can'?t": {"type": "contradiction", "severity": 0.75},
    r"i\s+forgot": {"type": "behavioral", "severity": 0.6},
    r"never\s+mind": {"type": "contradiction", "severity": 0.6},
    r"forget\s+it": {"type": "contradiction", "severity": 0.65},
}

# Time-related patterns for deadline extraction
DEADLINE_PATTERNS = {
    r"明天": {"seconds": 86400, "desc": "tomorrow"},
    r"后天": {"seconds": 172800, "desc": "day after tomorrow"},
    r"下周": {"seconds": 604800, "desc": "next week"},
    r"今晚": {"seconds": 43200, "desc": "tonight"},
    r"待会": {"seconds": 3600, "desc": "later"},
    r"一会儿": {"seconds": 1800, "desc": "in a while"},
    r"tomorrow": {"seconds": 86400, "desc": "tomorrow"},
    r"next\s+week": {"seconds": 604800, "desc": "next week"},
    r"in\s+(\d+)\s+hours?": {"seconds": lambda m: int(m.group(1)) * 3600, "desc": "in X hours"},
    r"in\s+(\d+)\s+minutes?": {"seconds": lambda m: int(m.group(1)) * 60, "desc": "in X minutes"},
    r"at\s+(\d+)(?::(\d+))?\s*(am|pm)?": {"seconds": None, "desc": "specific time"},  # Needs special handling
    r"(\d+)点": {"seconds": None, "desc": "at X o'clock"},  # Needs special handling
}


def generate_promise_id(promiser: str, promisee: str, content: str, timestamp: float) -> str:
    """Generate a unique promise ID."""
    data = f"{promiser}:{promisee}:{content}:{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def extract_promise_content(text: str, pattern_match: re.Match) -> str:
    """Extract what was promised from the text."""
    if pattern_match.lastindex and pattern_match.lastindex >= 1:
        content = pattern_match.group(1).strip()
        # Clean up common endings
        content = re.sub(r'[。！？.!?]+$', '', content)
        return content
    return text


def extract_deadline(text: str) -> Optional[float]:
    """
    Extract deadline from promise text.
    
    Returns:
        Unix timestamp of deadline, or None if no deadline found.
    """
    text_lower = text.lower()
    
    for pattern, info in DEADLINE_PATTERNS.items():
        match = re.search(pattern, text_lower)
        if match:
            seconds = info["seconds"]
            if callable(seconds):
                seconds = seconds(match)
            if seconds:
                return time.time() + seconds
    
    return None


def detect_promise(text: str, actor: str, target: str) -> Optional[Promise]:
    """
    Detect if a text contains a promise.
    
    Args:
        text: The text to analyze
        actor: Who is speaking/making the promise
        target: Who is receiving the promise
    
    Returns:
        Promise if detected, None otherwise
    """
    if not text:
        return None
    
    text_lower = text.lower()
    best_match = None
    best_confidence = 0.0
    best_content = ""
    
    for pattern, meta in PROMISE_PATTERNS.items():
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            confidence = meta["confidence"]
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = match
                best_content = extract_promise_content(text, match)
    
    if best_match is None:
        return None
    
    # Adjust confidence based on context
    # Higher confidence if addressed directly to target
    if target in text or target.split(":")[-1] in text:
        best_confidence = min(1.0, best_confidence + 0.1)
    
    # Lower confidence if vague
    if len(best_content) < 5:
        best_confidence *= 0.7
    
    timestamp = time.time()
    promise_id = generate_promise_id(actor, target, best_content, timestamp)
    deadline = extract_deadline(text)
    
    return Promise(
        promise_id=promise_id,
        promiser=actor,
        promisee=target,
        content=best_content,
        created_at=timestamp,
        deadline=deadline,
        conditions=[],
        confidence=best_confidence,
        evidence=text,
        status="active"
    )


def detect_violation_in_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Detect if a text indicates a violation/contradiction.
    
    Returns:
        Dict with violation type and severity, or None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    best_match = None
    best_severity = 0.0
    best_type = None
    
    for pattern, info in VIOLATION_PATTERNS.items():
        match = re.search(pattern, text_lower)
        if match:
            if info["severity"] > best_severity:
                best_severity = info["severity"]
                best_match = match
                best_type = info["type"]
    
    if best_match is None:
        return None
    
    return {
        "type": best_type,
        "severity": best_severity,
        "evidence": text,
        "matched_text": best_match.group(0)
    }


class PromiseLedger:
    """
    Promise/Contract Ledger for tracking promises and detecting violations.
    
    A betrayal requires evidence:
    1. An active promise exists
    2. A violation is detected (timeout, contradiction, or behavioral)
    
    Without both, we fall back to semantic classification with lower confidence.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "./data/emotiond.db"
        self._cache: Dict[str, Promise] = {}
    
    async def _get_db(self):
        """Get database connection."""
        return aiosqlite.connect(self.db_path)
    
    async def record_promise(self, promise: Promise) -> str:
        """
        Record a new promise.
        
        Args:
            promise: The promise to record
        
        Returns:
            The promise_id
        """
        async with await self._get_db() as db:
            await db.execute(
                """INSERT OR REPLACE INTO promises 
                   (promise_id, promiser, promisee, content, created_at, deadline, 
                    conditions, confidence, evidence, status, fulfilled_at, broken_at, broken_evidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (promise.promise_id, promise.promiser, promise.promisee, promise.content,
                 promise.created_at, promise.deadline, json.dumps(promise.conditions),
                 promise.confidence, promise.evidence, promise.status,
                 promise.fulfilled_at, promise.broken_at, promise.broken_evidence)
            )
            await db.commit()
        
        # Update cache
        self._cache[promise.promise_id] = promise
        return promise.promise_id
    
    async def mark_fulfilled(self, promise_id: str, evidence: str) -> bool:
        """
        Mark a promise as fulfilled.
        
        Args:
            promise_id: ID of the promise
            evidence: Evidence of fulfillment
        
        Returns:
            True if successful, False if promise not found
        """
        async with await self._get_db() as db:
            cursor = await db.execute(
                "SELECT status FROM promises WHERE promise_id = ?",
                (promise_id,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return False
            
            if row[0] != "active":
                return False  # Already fulfilled or broken
            
            await db.execute(
                """UPDATE promises 
                   SET status = 'fulfilled', fulfilled_at = ?, evidence = ? 
                   WHERE promise_id = ?""",
                (time.time(), f"{evidence}", promise_id)
            )
            await db.commit()
        
        # Update cache
        if promise_id in self._cache:
            self._cache[promise_id].status = "fulfilled"
            self._cache[promise_id].fulfilled_at = time.time()
        
        return True
    
    async def mark_broken(self, promise_id: str, evidence: str) -> bool:
        """
        Mark a promise as broken.
        
        Args:
            promise_id: ID of the promise
            evidence: Evidence of broken promise
        
        Returns:
            True if successful, False if promise not found
        """
        async with await self._get_db() as db:
            cursor = await db.execute(
                "SELECT status FROM promises WHERE promise_id = ?",
                (promise_id,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return False
            
            if row[0] != "active":
                return False  # Already fulfilled or broken
            
            await db.execute(
                """UPDATE promises 
                   SET status = 'broken', broken_at = ?, broken_evidence = ? 
                   WHERE promise_id = ?""",
                (time.time(), evidence, promise_id)
            )
            await db.commit()
        
        # Update cache
        if promise_id in self._cache:
            self._cache[promise_id].status = "broken"
            self._cache[promise_id].broken_at = time.time()
            self._cache[promise_id].broken_evidence = evidence
        
        return True
    
    async def get_active_promises(self, target_id: str) -> List[Promise]:
        """
        Get all active promises for a target (where target is the promisee).
        
        Args:
            target_id: The target to check
        
        Returns:
            List of active promises
        """
        async with await self._get_db() as db:
            cursor = await db.execute(
                """SELECT promise_id, promiser, promisee, content, created_at, deadline,
                          conditions, confidence, evidence, status, fulfilled_at, broken_at, broken_evidence
                   FROM promises 
                   WHERE promisee = ? AND status = 'active'
                   ORDER BY created_at DESC""",
                (target_id,)
            )
            rows = await cursor.fetchall()
            
            promises = []
            for row in rows:
                promise = Promise(
                    promise_id=row[0],
                    promiser=row[1],
                    promisee=row[2],
                    content=row[3],
                    created_at=row[4],
                    deadline=row[5],
                    conditions=json.loads(row[6]) if row[6] else [],
                    confidence=row[7],
                    evidence=row[8],
                    status=row[9],
                    fulfilled_at=row[10],
                    broken_at=row[11],
                    broken_evidence=row[12]
                )
                promises.append(promise)
                self._cache[promise.promise_id] = promise
            
            return promises
    
    async def get_promise_by_id(self, promise_id: str) -> Optional[Promise]:
        """Get a promise by its ID."""
        if promise_id in self._cache:
            return self._cache[promise_id]
        
        async with await self._get_db() as db:
            cursor = await db.execute(
                """SELECT promise_id, promiser, promisee, content, created_at, deadline,
                          conditions, confidence, evidence, status, fulfilled_at, broken_at, broken_evidence
                   FROM promises 
                   WHERE promise_id = ?""",
                (promise_id,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            promise = Promise(
                promise_id=row[0],
                promiser=row[1],
                promisee=row[2],
                content=row[3],
                created_at=row[4],
                deadline=row[5],
                conditions=json.loads(row[6]) if row[6] else [],
                confidence=row[7],
                evidence=row[8],
                status=row[9],
                fulfilled_at=row[10],
                broken_at=row[11],
                broken_evidence=row[12]
            )
            self._cache[promise_id] = promise
            return promise
    
    async def detect_violation(self, event: Any) -> Optional[ViolationResult]:
        """
        Detect if an event violates an active promise.
        
        Checks:
        1. Timeout - deadline passed without fulfillment
        2. Contradiction - explicit "I can't" or "I won't" after promise
        3. Behavioral - promised X but did Y
        
        Args:
            event: The event to check
        
        Returns:
            ViolationResult if violation detected, None otherwise
        """
        # Determine actor and target
        if event.type == "user_message":
            actor = event.actor
            target = event.target
            text = event.text
        elif event.type == "world_event":
            actor = event.actor
            target = event.target
            text = event.text
        else:
            return None
        
        # Get active promises where this actor is the promiser
        async with await self._get_db() as db:
            cursor = await db.execute(
                """SELECT promise_id, promiser, promisee, content, created_at, deadline,
                          conditions, confidence, evidence, status, fulfilled_at, broken_at, broken_evidence
                   FROM promises 
                   WHERE promiser = ? AND status = 'active'
                   ORDER BY created_at DESC""",
                (actor,)
            )
            rows = await cursor.fetchall()
        
        if not rows:
            return None
        
        now = time.time()
        
        for row in rows:
            promise = Promise(
                promise_id=row[0],
                promiser=row[1],
                promisee=row[2],
                content=row[3],
                created_at=row[4],
                deadline=row[5],
                conditions=json.loads(row[6]) if row[6] else [],
                confidence=row[7],
                evidence=row[8],
                status=row[9],
                fulfilled_at=row[10],
                broken_at=row[11],
                broken_evidence=row[12]
            )
            
            # Check 1: Timeout violation
            if promise.deadline and now > promise.deadline:
                return ViolationResult(
                    promise=promise,
                    violation_type="timeout",
                    evidence=f"Deadline passed: promised '{promise.content}' by {promise.deadline}, now is {now}",
                    severity=0.7,
                    timestamp=now
                )
            
            # Check 2: Contradiction in text
            if text:
                violation = detect_violation_in_text(text)
                if violation and violation["severity"] >= 0.6:
                    # Check if contradiction relates to the promise content
                    if self._is_related_to_promise(text, promise.content):
                        return ViolationResult(
                            promise=promise,
                            violation_type="contradiction",
                            evidence=f"Contradiction detected: '{violation['matched_text']}' after promise '{promise.content}'",
                            severity=violation["severity"],
                            timestamp=now
                        )
        
        return None
    
    def _is_related_to_promise(self, text: str, promise_content: str) -> bool:
        """
        Check if a text is related to a promise content.
        
        Simple heuristic: check for keyword overlap or negation of promise.
        """
        text_lower = text.lower()
        content_lower = promise_content.lower()
        
        # Check for "算了" or similar dismissive patterns - always indicates contradiction
        dismissive = ["算了", "不用了", "forget it", "never mind", "不能", "can't", "won't", "做不到"]
        for d in dismissive:
            if d in text_lower:
                return True
        
        # Check for negation patterns
        if len(content_lower) >= 5:
            negation_patterns = [
                r"不.+" + re.escape(content_lower[:8]),
                r"can'?t\s+.*" + re.escape(content_lower[:8]),
                r"won'?t\s+.*" + re.escape(content_lower[:8]),
            ]
            
            for pattern in negation_patterns:
                if re.search(pattern, text_lower):
                    return True
        
        return False
    
    async def check_timeout_violations(self) -> List[ViolationResult]:
        """
        Check all active promises for timeout violations.
        
        Returns:
            List of timeout violations found
        """
        now = time.time()
        violations = []
        
        async with await self._get_db() as db:
            cursor = await db.execute(
                """SELECT promise_id, promiser, promisee, content, created_at, deadline,
                          conditions, confidence, evidence, status
                   FROM promises 
                   WHERE status = 'active' AND deadline IS NOT NULL AND deadline < ?""",
                (now,)
            )
            rows = await cursor.fetchall()
        
        for row in rows:
            promise = Promise(
                promise_id=row[0],
                promiser=row[1],
                promisee=row[2],
                content=row[3],
                created_at=row[4],
                deadline=row[5],
                conditions=json.loads(row[6]) if row[6] else [],
                confidence=row[7],
                evidence=row[8],
                status=row[9]
            )
            
            violations.append(ViolationResult(
                promise=promise,
                violation_type="timeout",
                evidence=f"Deadline passed: promised '{promise.content}' by {promise.deadline}, now is {now}",
                severity=0.7,
                timestamp=now
            ))
        
        return violations
    
    async def get_all_promises(self, limit: int = 100) -> List[Promise]:
        """Get all promises, most recent first."""
        async with await self._get_db() as db:
            cursor = await db.execute(
                """SELECT promise_id, promiser, promisee, content, created_at, deadline,
                          conditions, confidence, evidence, status, fulfilled_at, broken_at, broken_evidence
                   FROM promises 
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            
            return [Promise(
                promise_id=row[0],
                promiser=row[1],
                promisee=row[2],
                content=row[3],
                created_at=row[4],
                deadline=row[5],
                conditions=json.loads(row[6]) if row[6] else [],
                confidence=row[7],
                evidence=row[8],
                status=row[9],
                fulfilled_at=row[10],
                broken_at=row[11],
                broken_evidence=row[12]
            ) for row in rows]
    
    async def clear_cache(self):
        """Clear the promise cache."""
        self._cache.clear()
    
    async def cleanup_old_promises(self, max_age_days: int = 30):
        """Clean up old fulfilled/broken promises."""
        cutoff = time.time() - (max_age_days * 86400)
        
        async with await self._get_db() as db:
            await db.execute(
                """DELETE FROM promises 
                   WHERE status IN ('fulfilled', 'broken') 
                   AND (fulfilled_at < ? OR broken_at < ?)""",
                (cutoff, cutoff)
            )
            await db.commit()


# Global ledger instance
_ledger: Optional[PromiseLedger] = None


def get_ledger(db_path: str = None) -> PromiseLedger:
    """Get or create the global promise ledger."""
    global _ledger
    if _ledger is None:
        _ledger = PromiseLedger(db_path)
    return _ledger


async def init_ledger(db_path: str = None):
    """Initialize the promise ledger with database path."""
    global _ledger
    _ledger = PromiseLedger(db_path)
    return _ledger
