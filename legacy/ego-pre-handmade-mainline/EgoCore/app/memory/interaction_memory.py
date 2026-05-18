"""
OpenEmotion Agent Runtime - Interaction Memory

Handles recent interaction summaries and key decisions.
Provides short-term context about what happened recently.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.memory.memory_manager import (
    MemoryManager, MemoryEntry, MemoryType, get_memory_manager
)


class InteractionMemory:
    """
    Handler for interaction memory.
    
    Interaction memory contains:
    - Recent interaction summaries
    - Key decisions made in conversations
    - User requests and agent responses
    - Important context from recent sessions
    
    These memories have:
    - Short TTL (7 days)
    - Lower injection priority
    - Used for context awareness, not task continuity
    """
    
    # Interaction types
    TYPE_USER_REQUEST = "user_request"
    TYPE_AGENT_RESPONSE = "agent_response"
    TYPE_DECISION = "decision"
    TYPE_FEEDBACK = "feedback"
    
    def __init__(self, manager: Optional[MemoryManager] = None):
        """
        Initialize interaction memory handler.
        
        Args:
            manager: Memory manager instance
        """
        self._manager = manager or get_memory_manager()
    
    def save_interaction(self,
                        summary: str,
                        decisions: Optional[List[str]] = None,
                        context: Optional[Dict[str, Any]] = None,
                        interaction_type: Optional[str] = None,
                        related_task_id: Optional[str] = None) -> MemoryEntry:
        """
        Save interaction memory.
        
        This should be called:
        - After significant user-agent exchanges
        - When important decisions are made
        - When user provides feedback
        
        Args:
            summary: Interaction summary (concise)
            decisions: Key decisions made during interaction
            context: Additional context (task info, etc.)
            interaction_type: Type of interaction
            related_task_id: Associated task if any
        
        Returns:
            Created memory entry
        """
        metadata = {
            'decisions': decisions or [],
            'context': context or {},
            'interaction_type': interaction_type or 'general',
            'related_task_id': related_task_id
        }
        
        # Generate key with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        key = f"interaction:{timestamp}"
        
        entry = MemoryEntry.create(
            memory_type=MemoryType.INTERACTION,
            key=key,
            content=summary,
            metadata=metadata
        )
        
        return self._manager.save(entry)
    
    def save_user_request(self, request: str,
                         related_task_id: Optional[str] = None) -> MemoryEntry:
        """
        Save a user request.
        
        Args:
            request: User's request text
            related_task_id: Associated task if any
        
        Returns:
            Created memory entry
        """
        return self.save_interaction(
            summary=f"User requested: {request[:200]}",
            interaction_type=self.TYPE_USER_REQUEST,
            related_task_id=related_task_id
        )
    
    def save_agent_response(self, response: str,
                           related_task_id: Optional[str] = None) -> MemoryEntry:
        """
        Save an agent response.
        
        Args:
            response: Agent's response summary
            related_task_id: Associated task if any
        
        Returns:
            Created memory entry
        """
        return self.save_interaction(
            summary=f"Agent responded: {response[:200]}",
            interaction_type=self.TYPE_AGENT_RESPONSE,
            related_task_id=related_task_id
        )
    
    def save_decision(self, decision: str,
                     rationale: Optional[str] = None,
                     related_task_id: Optional[str] = None) -> MemoryEntry:
        """
        Save a decision made during interaction.
        
        Args:
            decision: Decision description
            rationale: Why this decision was made
            related_task_id: Associated task if any
        
        Returns:
            Created memory entry
        """
        summary = f"Decision: {decision}"
        if rationale:
            summary += f" (Rationale: {rationale})"
        
        return self.save_interaction(
            summary=summary,
            decisions=[decision],
            interaction_type=self.TYPE_DECISION,
            related_task_id=related_task_id
        )
    
    def save_feedback(self, feedback: str,
                     related_task_id: Optional[str] = None) -> MemoryEntry:
        """
        Save user feedback.
        
        Args:
            feedback: User's feedback
            related_task_id: Associated task if any
        
        Returns:
            Created memory entry
        """
        return self.save_interaction(
            summary=f"User feedback: {feedback}",
            interaction_type=self.TYPE_FEEDBACK,
            related_task_id=related_task_id
        )
    
    def get_recent_interactions(self, limit: int = 10) -> List[MemoryEntry]:
        """
        Get recent interactions.
        
        Args:
            limit: Maximum number of interactions to return
        
        Returns:
            List of recent interaction entries
        """
        return self._manager.list_by_type(MemoryType.INTERACTION, limit=limit)
    
    def get_interactions_for_task(self, task_id: str,
                                  limit: int = 20) -> List[MemoryEntry]:
        """
        Get interactions related to a specific task.
        
        Args:
            task_id: Task identifier
            limit: Maximum number of interactions
        
        Returns:
            List of related interaction entries
        """
        all_interactions = self._manager.list_by_type(MemoryType.INTERACTION, limit=limit)
        
        # Filter by related_task_id
        return [
            i for i in all_interactions
            if i.metadata.get('related_task_id') == task_id
        ]
    
    def get_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent decisions.
        
        Args:
            limit: Maximum number of decisions
        
        Returns:
            List of decision entries
        """
        interactions = self.get_recent_interactions(limit=limit * 2)
        
        decisions = []
        for interaction in interactions:
            if interaction.metadata.get('interaction_type') == self.TYPE_DECISION:
                decisions.append({
                    'decision': interaction.content,
                    'created_at': interaction.created_at.isoformat(),
                    'related_task_id': interaction.metadata.get('related_task_id')
                })
        
        return decisions[:limit]
    
    def cleanup_old_interactions(self, days: int = 7) -> int:
        """
        Clean up interactions older than specified days.
        
        Args:
            days: Number of days to keep
        
        Returns:
            Number of entries deleted
        """
        interactions = self._manager.list_by_type(MemoryType.INTERACTION, limit=1000)
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0
        
        for interaction in interactions:
            if interaction.created_at < cutoff:
                self._manager.delete(interaction.id)
                deleted += 1
        
        return deleted
    
    def build_context_string(self, limit: int = 5) -> str:
        """
        Build context string for injection.
        
        Args:
            limit: Maximum number of interactions to include
        
        Returns:
            Formatted string of recent interactions
        """
        interactions = self.get_recent_interactions(limit=limit)
        
        if not interactions:
            return ""
        
        lines = ["## Recent Interactions"]
        
        for interaction in interactions:
            timestamp = interaction.created_at.strftime('%Y-%m-%d %H:%M')
            interaction_type = interaction.metadata.get('interaction_type', 'general')
            
            type_emoji = {
                self.TYPE_USER_REQUEST: "👤",
                self.TYPE_AGENT_RESPONSE: "🤖",
                self.TYPE_DECISION: "💡",
                self.TYPE_FEEDBACK: "📝",
                'general': "💬"
            }.get(interaction_type, "💬")
            
            lines.append(f"{type_emoji} [{timestamp}] {interaction.content[:150]}")
        
        return "\n".join(lines)
    
    def build_summary(self) -> Dict[str, Any]:
        """
        Build summary of recent interactions.
        
        Returns:
            Dict with interaction statistics
        """
        interactions = self.get_recent_interactions(limit=100)
        
        summary = {
            'total_count': len(interactions),
            'by_type': {},
            'recent_decisions': [],
            'has_interactions': len(interactions) > 0
        }
        
        # Count by type
        for interaction in interactions:
            interaction_type = interaction.metadata.get('interaction_type', 'general')
            summary['by_type'][interaction_type] = summary['by_type'].get(interaction_type, 0) + 1
        
        # Get recent decisions
        summary['recent_decisions'] = self.get_decisions(limit=5)
        
        return summary


def get_interaction_handler() -> InteractionMemory:
    """Get interaction memory handler instance."""
    return InteractionMemory()
