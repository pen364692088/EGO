"""
Testbot Harness - Core adapter for message-to-event conversion.

Converts testbot messages to emotiond events and writes them
to run.jsonl for deterministic replay.
"""
import json
import os
import time
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    ConversationContext,
    ConversationTapeEntry,
)
from emotiond.models import Event


class TestbotHarness:
    """
    Harness for converting testbot messages to emotiond events.
    
    Key responsibilities:
    1. Convert TestbotMessage → Event (emotiond format)
    2. Write entries to run.jsonl (conversation tape)
    3. Track conversation context (turn_id, channel, thread_id)
    4. Provide isolation between different test runs
    """
    
    def __init__(self, config: Optional[TestbotConfig] = None):
        """Initialize harness with optional config."""
        self.config = config or TestbotConfig()
        self.context = ConversationContext(
            channel=self.config.channel,
            thread_id=self.config.thread_id,
        )
        self._tape_entries: List[ConversationTapeEntry] = []
        self._run_file: Optional[Path] = None
        
        if self.config.log_to_file:
            self._init_run_file()
    
    def _init_run_file(self) -> None:
        """Initialize the run.jsonl file for this test run."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        run_id = self.config.run_id or self._generate_run_id()
        self._run_file = output_dir / f"{run_id}.jsonl"
        
        # Write header entry
        header = {
            "type": "run_start",
            "ts": time.time(),
            "run_id": run_id,
            "channel": self.config.channel,
            "thread_id": self.config.thread_id,
            "config": self.config.model_dump(),
        }
        self._append_to_tape(header)
    
    def _generate_run_id(self) -> str:
        """Generate a unique run ID based on timestamp."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"run_{ts}_{self.config.thread_id}"
    
    def _append_to_tape(self, entry: Dict[str, Any]) -> None:
        """Append entry to tape file and in-memory list."""
        if isinstance(entry, dict) and "type" in entry:
            self._tape_entries.append(ConversationTapeEntry(**entry))
        else:
            self._tape_entries.append(entry)
        
        if self._run_file:
            with open(self._run_file, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def process_message(self, message: TestbotMessage) -> Dict[str, Any]:
        """
        Process a testbot message and return event.
        
        This is the main entry point for message conversion.
        It converts the testbot message to an emotiond Event,
        writes it to the tape, and returns the event data.
        
        Args:
            message: TestbotMessage to process
            
        Returns:
            Dict with event data and metadata
        """
        # Advance turn counter
        turn_id = self.context.next_turn()
        
        # Create emotiond Event
        event = Event(
            type="user_message",
            actor=message.sender,
            target="agent",
            text=message.text,
            meta={
                "message_id": message.message_id,
                "turn_id": turn_id,
                "channel": self.config.channel,
                "thread_id": self.config.thread_id,
                "sender_id": message.sender_id,
                "timestamp": message.timestamp,
                "testbot": True,  # Mark as testbot origin
            }
        )
        
        # Write inbound message to tape
        tape_entry = {
            "type": "inbound",
            "ts": message.ts or time.time(),
            "message_id": message.message_id,
            "sender": message.sender,
            "text": message.text,
            "turn_id": turn_id,
            "channel": self.config.channel,
            "thread_id": self.config.thread_id,
        }
        self._append_to_tape(tape_entry)
        
        # Update context
        self.context.increment_message()
        
        return {
            "event": event.model_dump(),
            "turn_id": turn_id,
            "message_id": message.message_id,
        }
    
    async def process_and_dispatch(self, message: TestbotMessage) -> Dict[str, Any]:
        """
        Process message and dispatch to emotiond.
        
        This calls process_message() and then dispatches the
        resulting event to emotiond.core.process_event().
        
        Args:
            message: TestbotMessage to process
            
        Returns:
            Dict with event data and process_event result
        """
        from emotiond.core import process_event
        
        # Convert message to event
        result = self.process_message(message)
        
        # Create Event object for dispatch
        event = Event(**result["event"])
        
        # Dispatch to emotiond
        process_result = await process_event(event)
        
        # Write tool call entry
        tool_entry = {
            "type": "tool_call",
            "ts": time.time(),
            "tool": "process_event",
            "args": {
                "type": event.type,
                "actor": event.actor,
                "target": event.target,
                "text": event.text,
            },
            "turn_id": result["turn_id"],
        }
        self._append_to_tape(tool_entry)
        
        # Write tool return entry
        return_entry = {
            "type": "tool_return",
            "ts": time.time(),
            "result": process_result,
            "turn_id": result["turn_id"],
        }
        self._append_to_tape(return_entry)
        
        return {
            **result,
            "process_result": process_result,
        }
    
    def record_outbound(
        self, 
        text: str, 
        message_id: Optional[str] = None,
        turn_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record an outbound (agent) message.
        
        Args:
            text: Agent response text
            message_id: Optional message ID
            turn_id: Turn ID (defaults to current)
            
        Returns:
            Dict with recorded entry data
        """
        turn_id = turn_id or self.context.turn_id
        ts = time.time()
        
        entry = {
            "type": "outbound",
            "ts": ts,
            "message_id": message_id or f"agent_{turn_id}",
            "text": text,
            "turn_id": turn_id,
            "channel": self.config.channel,
            "thread_id": self.config.thread_id,
        }
        self._append_to_tape(entry)
        
        return entry
    
    def finalize(self) -> Dict[str, Any]:
        """
        Finalize the test run and return summary.
        
        Writes a run_end entry and returns statistics.
        """
        end_entry = {
            "type": "run_end",
            "ts": time.time(),
            "message_count": self.context.message_count,
            "turn_count": self.context.turn_id,
        }
        self._append_to_tape(end_entry)
        
        # Calculate tape hash for deterministic verification
        tape_hash = self.calculate_tape_hash()
        
        return {
            "run_id": self._run_file.stem if self._run_file else None,
            "tape_path": str(self._run_file) if self._run_file else None,
            "message_count": self.context.message_count,
            "turn_count": self.context.turn_id,
            "tape_hash": tape_hash,
        }
    
    def calculate_tape_hash(self) -> str:
        """
        Calculate SHA256 hash of tape entries.
        
        Used for deterministic verification that
        two runs produce identical trajectories.
        """
        # Only hash the meaningful entries (exclude run_start/run_end)
        hashable_entries = [
            e for e in self._tape_entries 
            if isinstance(e, ConversationTapeEntry) 
            and e.type not in ("run_start", "run_end")
        ]
        
        # Create canonical JSON representation
        canonical = json.dumps(
            [e.model_dump() for e in hashable_entries],
            sort_keys=True,
            ensure_ascii=False
        )
        
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def get_tape_entries(self) -> List[Dict[str, Any]]:
        """Get all tape entries as dictionaries."""
        return [
            e.model_dump() if isinstance(e, ConversationTapeEntry) else e
            for e in self._tape_entries
        ]


def process_testbot_message(
    message: TestbotMessage,
    config: Optional[TestbotConfig] = None
) -> Dict[str, Any]:
    """
    Convenience function to process a single testbot message.
    
    Creates a harness instance, processes the message,
    and returns the event data.
    
    Args:
        message: TestbotMessage to process
        config: Optional TestbotConfig
        
    Returns:
        Dict with event data
    """
    harness = TestbotHarness(config)
    return harness.process_message(message)


async def run_conversation(
    messages: List[TestbotMessage],
    config: Optional[TestbotConfig] = None,
    dispatch: bool = True
) -> Dict[str, Any]:
    """
    Run a full conversation through the harness.
    
    Processes all messages and returns results including
    tape hash for deterministic verification.
    
    Args:
        messages: List of TestbotMessages
        config: Optional TestbotConfig
        dispatch: Whether to dispatch to emotiond (default True)
        
    Returns:
        Dict with run results and tape hash
    """
    harness = TestbotHarness(config)
    results = []
    
    for message in messages:
        if dispatch:
            result = await harness.process_and_dispatch(message)
        else:
            result = harness.process_message(message)
        results.append(result)
    
    summary = harness.finalize()
    summary["results"] = results
    
    return summary
