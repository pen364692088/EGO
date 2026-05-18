"""
Memory system for storing and recalling events with summarization
"""
import time
from typing import Dict, Any, List
from emotiond.db import get_recent_events, get_events_by_target, add_event
from emotiond.config import is_core_disabled


class MemorySystem:
    """Memory system for event storage, recall, and summarization"""
    
    def __init__(self):
        self.memory_strength = 1.0  # Base memory strength
        self.summarization_interval = 120  # Summarize every 2 minutes
        self.last_summarization = 0  # Initialize to 0 so first summarization can run immediately
        self.target_memories: Dict[str, Dict[str, Any]] = {}
    
    def calculate_memory_strength(self, prediction_error: float, arousal: float) -> float:
        """Calculate memory strength based on prediction error and arousal"""
        if is_core_disabled():
            return 1.0
        
        # Memory strength increases with prediction error and arousal
        strength_modifier = 1.0 + (prediction_error * 0.5) + (arousal * 0.3)
        return min(3.0, self.memory_strength * strength_modifier)
    
    async def summarize_memories(self) -> Dict[str, Any]:
        """Summarize recent events and update target memories"""
        if is_core_disabled():
            return {"status": "disabled"}
        
        current_time = time.time()
        
        # Check if it's time for summarization
        if current_time - self.last_summarization < self.summarization_interval:
            return {"status": "not_due"}
        
        # Get recent events for summarization
        recent_events = await get_recent_events(limit=100)
        
        # Group events by target
        target_summaries: Dict[str, Dict[str, Any]] = {}
        for event in recent_events:
            target = event["target"]
            if target not in target_summaries:
                target_summaries[target] = {
                    "event_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "recent_interaction": "",
                    "last_interaction": ""
                }
            
            target_summaries[target]["event_count"] += 1
            
            # Classify events as positive or negative
            if event["type"] == "user_message":
                if event["text"] and any(word in event["text"].lower() for word in ["good", "great", "thanks", "love", "happy", "wonderful", "amazing", "excellent", "fantastic", "awesome", "beautiful", "nice", "best"]):
                    target_summaries[target]["positive_count"] += 1
                elif event["text"] and any(word in event["text"].lower() for word in ["bad", "hate", "stupid", "wrong", "angry", "terrible", "awful", "horrible"]):
                    target_summaries[target]["negative_count"] += 1
            
            # Track most recent interaction
            if not target_summaries[target]["recent_interaction"]:
                target_summaries[target]["recent_interaction"] = event["type"]
                target_summaries[target]["last_interaction"] = event["created_at"]
        
        # Store target memories
        self.target_memories = target_summaries
        self.last_summarization = current_time
        
        # Create a summary event
        summary_event = {
            "type": "memory_summary",
            "actor": "system",
            "target": "all",
            "text": f"Memory summary completed for {len(target_summaries)} targets",
            "meta": {
                "target_summaries": target_summaries,
                "total_events": len(recent_events)
            }
        }
        
        # Store the summary event
        await add_event(summary_event)
        
        return {
            "status": "completed",
            "target_summaries": target_summaries,
            "total_events": len(recent_events)
        }
    
    async def get_target_memory_summary(self, target: str) -> Dict[str, Any]:
        """Get memory summary for a specific target"""
        if target in self.target_memories:
            return self.target_memories[target]
        
        # If no summary exists, create one from recent events
        target_events = await get_events_by_target(target, limit=20)
        
        summary: Dict[str, Any] = {
            "event_count": len(target_events),
            "positive_count": 0,
            "negative_count": 0,
            "recent_interaction": "",
            "last_interaction": ""
        }
        
        for event in target_events:
            if event["type"] == "user_message":
                if event["text"] and any(word in event["text"].lower() for word in ["good", "great", "thanks", "love", "happy", "wonderful", "amazing", "excellent", "fantastic", "awesome", "beautiful", "nice", "best"]):
                    summary["positive_count"] += 1
                elif event["text"] and any(word in event["text"].lower() for word in ["bad", "hate", "stupid", "wrong", "angry", "terrible", "awful", "horrible"]):
                    summary["negative_count"] += 1
            
            if not summary["recent_interaction"]:
                summary["recent_interaction"] = event["type"]
                summary["last_interaction"] = event["created_at"]
        
        return summary
    
    def get_memory_impact_on_relationship(self, target: str) -> Dict[str, float]:
        """Calculate how historical memories should affect current relationships"""
        if is_core_disabled() or target not in self.target_memories:
            return {"bond_modifier": 0.0, "grudge_modifier": 0.0}
        
        memory = self.target_memories[target]
        
        # Calculate modifiers based on historical interactions
        total_interactions = memory["event_count"]
        if total_interactions == 0:
            return {"bond_modifier": 0.0, "grudge_modifier": 0.0}
        
        positive_ratio = memory["positive_count"] / total_interactions
        negative_ratio = memory["negative_count"] / total_interactions
        
        # Historical patterns influence current relationship updates
        bond_modifier = positive_ratio * 0.1 - negative_ratio * 0.05
        grudge_modifier = negative_ratio * 0.1 - positive_ratio * 0.05
        
        return {
            "bond_modifier": bond_modifier,
            "grudge_modifier": grudge_modifier
        }


# Global memory system instance
memory_system = MemorySystem()


async def initialize_memory_system():
    """Initialize memory system on startup"""
    # Perform initial memory summarization
    await memory_system.summarize_memories()