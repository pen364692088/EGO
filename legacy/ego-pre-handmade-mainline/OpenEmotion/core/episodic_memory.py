"""
Episodic Memory v0 (US-702)

Implements episode storage with provenance, retrieval, and continuity.
Episodes must have provenance+signature to prevent injection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Episode:
    """
    A single episode in memory.
    
    Episodes represent discrete events with emotional significance.
    All episodes must have provenance to prevent injection.
    
    Attributes:
        event: The event that occurred
        appraisal: The emotional appraisal of the event
        state_delta: Changes to internal state
        action: Action taken in response
        outcome: Result of the action
        lesson: What was learned (optional)
        provenance: Source and signature information
        timestamp: When the episode occurred
        importance: Subjective importance (0-1)
    """
    event: str
    appraisal: Dict[str, float] = field(default_factory=dict)
    state_delta: Dict[str, Any] = field(default_factory=dict)
    action: str = ""
    outcome: str = ""
    lesson: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    importance: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "appraisal": self.appraisal,
            "state_delta": self.state_delta,
            "action": self.action,
            "outcome": self.outcome,
            "lesson": self.lesson,
            "provenance": self.provenance,
            "timestamp": self.timestamp,
            "importance": self.importance,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episode":
        return cls(
            event=data.get("event", ""),
            appraisal=data.get("appraisal", {}),
            state_delta=data.get("state_delta", {}),
            action=data.get("action", ""),
            outcome=data.get("outcome", ""),
            lesson=data.get("lesson", ""),
            provenance=data.get("provenance", {}),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            importance=data.get("importance", 0.5),
        )
    
    def compute_hash(self) -> str:
        """Compute hash for this episode."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EpisodeStore:
    """
    Storage for episodes with retrieval and management.
    
    Features:
    - Append with provenance validation
    - Query by various criteria
    - Top-K retrieval by importance/recency
    - TTL-based expiration
    - Size cap enforcement
    """
    
    def __init__(
        self,
        max_episodes: int = 1000,
        default_ttl_days: int = 30,
        enable_provenance_check: bool = True,
    ):
        self.episodes: List[Episode] = []
        self.max_episodes = max_episodes
        self.default_ttl_days = default_ttl_days
        self.enable_provenance_check = enable_provenance_check
        self._index: Dict[str, int] = {}  # hash -> position
    
    def append(self, episode: Episode, validate_provenance: bool = True) -> Tuple[bool, str]:
        """
        Append an episode to the store.
        
        Args:
            episode: The episode to append
            validate_provenance: Whether to validate provenance
        
        Returns:
            (success, reason) tuple
        """
        # Validate provenance
        if self.enable_provenance_check and validate_provenance:
            if not episode.provenance:
                return False, "missing_provenance"
            
            source = episode.provenance.get("source", "")
            signature = episode.provenance.get("signature")
            
            # Internal sources must have signature
            internal_sources = ["system", "inference", "rollout", "reflection", "memory"]
            if source in internal_sources and not signature:
                return False, "missing_signature_for_internal_source"
        
        # Check for duplicate
        ep_hash = episode.compute_hash()
        if ep_hash in self._index:
            return False, "duplicate_episode"
        
        # Enforce size cap
        if len(self.episodes) >= self.max_episodes:
            self._evict_oldest()
        
        # Add episode
        self.episodes.append(episode)
        self._index[ep_hash] = len(self.episodes) - 1
        
        return True, "ok"
    
    def query(
        self,
        event_contains: Optional[str] = None,
        min_importance: Optional[float] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Episode]:
        """
        Query episodes by various criteria.
        
        Args:
            event_contains: Filter by event text
            min_importance: Minimum importance threshold
            since: ISO timestamp for recency filter
            limit: Maximum results to return
        
        Returns:
            List of matching episodes
        """
        results = []
        
        for ep in reversed(self.episodes):  # Most recent first
            # Apply filters
            if event_contains and event_contains.lower() not in ep.event.lower():
                continue
            if min_importance is not None and ep.importance < min_importance:
                continue
            if since and ep.timestamp < since:
                continue
            
            results.append(ep)
            if len(results) >= limit:
                break
        
        return results
    
    def top_k(
        self,
        k: int = 10,
        by: str = "importance",
        min_importance: float = 0.0,
    ) -> List[Episode]:
        """
        Get top-K episodes by importance or recency.
        
        Args:
            k: Number of episodes to return
            by: Sort criterion ("importance" or "recency")
            min_importance: Minimum importance threshold
        
        Returns:
            Top K episodes
        """
        # Filter by minimum importance
        candidates = [ep for ep in self.episodes if ep.importance >= min_importance]
        
        # Sort
        if by == "importance":
            candidates.sort(key=lambda e: e.importance, reverse=True)
        elif by == "recency":
            candidates.sort(key=lambda e: e.timestamp, reverse=True)
        
        return candidates[:k]
    
    def get_relevant_summary(self, query: str, max_episodes: int = 5) -> Dict[str, Any]:
        """
        Get a summary of relevant episodes for a query.
        
        This injects only summaries and evidence pointers, not full context.
        
        Args:
            query: The query to match against
            max_episodes: Maximum episodes to include
        
        Returns:
            Summary with episode pointers
        """
        relevant = self.query(event_contains=query, limit=max_episodes)
        
        if not relevant:
            return {"episodes": [], "summary": "No relevant episodes found"}
        
        summaries = []
        for ep in relevant:
            summaries.append({
                "event_preview": ep.event[:100] + "..." if len(ep.event) > 100 else ep.event,
                "importance": ep.importance,
                "timestamp": ep.timestamp,
                "hash": ep.compute_hash()[:8],
            })
        
        # Generate summary (simplified - in practice would use LLM)
        summary = f"Found {len(relevant)} relevant episodes"
        
        return {
            "episodes": summaries,
            "summary": summary,
            "query": query,
        }
    
    def cleanup_expired(self) -> int:
        """
        Remove episodes past their TTL.
        
        Returns:
            Number of episodes removed
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.default_ttl_days)).isoformat()
        
        initial_count = len(self.episodes)
        self.episodes = [ep for ep in self.episodes if ep.timestamp >= cutoff]
        
        # Rebuild index
        self._index = {ep.compute_hash(): i for i, ep in enumerate(self.episodes)}
        
        return initial_count - len(self.episodes)
    
    def _evict_oldest(self) -> None:
        """Evict the oldest/least important episode."""
        if not self.episodes:
            return
        
        # Find oldest with lowest importance
        min_score = float("inf")
        min_idx = 0
        
        for i, ep in enumerate(self.episodes):
            # Score = age (lower timestamp) + low importance
            score = i - (ep.importance * 100)  # Older + less important = lower score
            if score < min_score:
                min_score = score
                min_idx = i
        
        # Remove
        old_hash = self.episodes[min_idx].compute_hash()
        del self._index[old_hash]
        self.episodes.pop(min_idx)
        
        # Rebuild index
        self._index = {ep.compute_hash(): i for i, ep in enumerate(self.episodes)}
    
    def __len__(self) -> int:
        return len(self.episodes)
    
    def __iter__(self):
        return iter(self.episodes)
