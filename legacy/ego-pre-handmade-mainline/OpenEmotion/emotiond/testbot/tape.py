"""
Conversation Tape - Recording and Replay Engine for Testbot Harness.

Provides deterministic recording and replay of conversations for testing
emotiond decision trajectories.

Key classes:
- TapeRecorder: Intercept process_event() calls, write to tape
- TapeReplayer: Read tape, feed messages to harness
- TapeHash: SHA256 hash calculation for deterministic validation
"""
import json
import os
import time
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, field

from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    ConversationContext,
    ConversationTapeEntry,
)
from emotiond.testbot.harness import TestbotHarness


@dataclass
class TapeEntry:
    """Single entry in conversation tape."""
    type: str
    ts: float
    message_id: Optional[str] = None
    sender: Optional[str] = None
    sender_id: Optional[str] = None
    text: Optional[str] = None
    turn_id: Optional[int] = None
    channel: Optional[str] = None
    thread_id: Optional[str] = None
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    message_count: Optional[int] = None
    turn_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, omitting None values."""
        d = {"type": self.type, "ts": self.ts}
        if self.message_id is not None:
            d["message_id"] = self.message_id
        if self.sender is not None:
            d["sender"] = self.sender
        if self.sender_id is not None:
            d["sender_id"] = self.sender_id
        if self.text is not None:
            d["text"] = self.text
        if self.turn_id is not None:
            d["turn_id"] = self.turn_id
        if self.channel is not None:
            d["channel"] = self.channel
        if self.thread_id is not None:
            d["thread_id"] = self.thread_id
        if self.tool is not None:
            d["tool"] = self.tool
        if self.args is not None:
            d["args"] = self.args
        if self.result is not None:
            d["result"] = self.result
        if self.run_id is not None:
            d["run_id"] = self.run_id
        if self.config is not None:
            d["config"] = self.config
        if self.message_count is not None:
            d["message_count"] = self.message_count
        if self.turn_count is not None:
            d["turn_count"] = self.turn_count
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TapeEntry":
        """Create from dictionary."""
        return cls(
            type=data["type"],
            ts=data["ts"],
            message_id=data.get("message_id"),
            sender=data.get("sender"),
            sender_id=data.get("sender_id"),
            text=data.get("text"),
            turn_id=data.get("turn_id"),
            channel=data.get("channel"),
            thread_id=data.get("thread_id"),
            tool=data.get("tool"),
            args=data.get("args"),
            result=data.get("result"),
            run_id=data.get("run_id"),
            config=data.get("config"),
            message_count=data.get("message_count"),
            turn_count=data.get("turn_count"),
        )


class TapeRecorder:
    """
    Records conversation events to a tape file.
    
    Intercepts process_event() calls and writes all messages,
    tool calls, and results to a JSONL tape file.
    
    Usage:
        recorder = TapeRecorder(config)
        result = await recorder.record_inbound(message, turn_id)
        await recorder.record_tool_call("process_event", args, turn_id)
        await recorder.record_tool_return(result, turn_id)
        tape_hash = recorder.finalize()
    """
    
    def __init__(
        self,
        config: Optional[TestbotConfig] = None,
        output_dir: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        """
        Initialize tape recorder.
        
        Args:
            config: Testbot configuration
            output_dir: Override output directory
            run_id: Override run ID
        """
        self.config = config or TestbotConfig()
        self.output_dir = Path(output_dir or self.config.output_dir)
        self.run_id = run_id or self.config.run_id or self._generate_run_id()
        
        self._entries: List[TapeEntry] = []
        self._tape_file: Optional[Path] = None
        self._finalized = False
        self._start_ts: Optional[float] = None
        
        # Initialize output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID based on timestamp."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"tape_{ts}_{self.config.thread_id}"
    
    def _append_entry(self, entry: TapeEntry) -> None:
        """Append entry to in-memory list and optionally write to file."""
        if self._finalized:
            raise RuntimeError("Cannot append to finalized tape")
        
        self._entries.append(entry)
        
        # Write to file if initialized
        if self._tape_file:
            with open(self._tape_file, "a") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def start(self) -> str:
        """
        Start recording and return run_id.
        
        Creates the tape file and writes run_start entry.
        """
        if self._start_ts is not None:
            raise RuntimeError("Recording already started")
        
        self._start_ts = time.time()
        self._tape_file = self.output_dir / f"{self.run_id}.jsonl"
        
        # Write run_start entry
        entry = TapeEntry(
            type="run_start",
            ts=self._start_ts,
            run_id=self.run_id,
            channel=self.config.channel,
            thread_id=self.config.thread_id,
            config=self.config.model_dump(),
        )
        self._append_entry(entry)
        
        return self.run_id
    
    def record_inbound(
        self,
        message: TestbotMessage,
        turn_id: int,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record an inbound (user) message.
        
        Args:
            message: The testbot message
            turn_id: Current turn number
            ts: Optional timestamp (defaults to now)
            
        Returns:
            Dict with recorded entry data
        """
        if self._start_ts is None:
            self.start()
        
        entry = TapeEntry(
            type="inbound",
            ts=ts or time.time(),
            message_id=message.message_id,
            sender=message.sender,
            sender_id=message.sender_id,
            text=message.text,
            turn_id=turn_id,
            channel=self.config.channel,
            thread_id=self.config.thread_id,
        )
        self._append_entry(entry)
        
        return entry.to_dict()
    
    def record_outbound(
        self,
        text: str,
        turn_id: int,
        message_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record an outbound (agent) message.
        
        Args:
            text: Agent response text
            turn_id: Current turn number
            message_id: Optional message ID
            ts: Optional timestamp
            
        Returns:
            Dict with recorded entry data
        """
        if self._start_ts is None:
            self.start()
        
        entry = TapeEntry(
            type="outbound",
            ts=ts or time.time(),
            message_id=message_id or f"agent_{turn_id}",
            text=text,
            turn_id=turn_id,
            channel=self.config.channel,
            thread_id=self.config.thread_id,
        )
        self._append_entry(entry)
        
        return entry.to_dict()
    
    def record_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        turn_id: int,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record a tool call.
        
        Args:
            tool: Tool name (e.g., "process_event")
            args: Tool arguments
            turn_id: Current turn number
            ts: Optional timestamp
            
        Returns:
            Dict with recorded entry data
        """
        if self._start_ts is None:
            self.start()
        
        entry = TapeEntry(
            type="tool_call",
            ts=ts or time.time(),
            tool=tool,
            args=args,
            turn_id=turn_id,
        )
        self._append_entry(entry)
        
        return entry.to_dict()
    
    def record_tool_return(
        self,
        result: Dict[str, Any],
        turn_id: int,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record a tool return result.
        
        Args:
            result: Tool result
            turn_id: Current turn number
            ts: Optional timestamp
            
        Returns:
            Dict with recorded entry data
        """
        if self._start_ts is None:
            self.start()
        
        entry = TapeEntry(
            type="tool_return",
            ts=ts or time.time(),
            result=result,
            turn_id=turn_id,
        )
        self._append_entry(entry)
        
        return entry.to_dict()
    
    def finalize(self) -> Dict[str, Any]:
        """
        Finalize the tape and return summary.
        
        Writes run_end entry and returns statistics including
        the tape hash for deterministic verification.
        
        Returns:
            Dict with run_id, tape_path, message_count, turn_count, tape_hash
        """
        if self._finalized:
            raise RuntimeError("Tape already finalized")
        
        if self._start_ts is None:
            self.start()
        
        # Count turns and messages
        turn_ids = set()
        message_count = 0
        for entry in self._entries:
            if entry.turn_id is not None:
                turn_ids.add(entry.turn_id)
            if entry.type in ("inbound", "outbound"):
                message_count += 1
        
        # Write run_end entry
        end_entry = TapeEntry(
            type="run_end",
            ts=time.time(),
            message_count=message_count,
            turn_count=len(turn_ids),
        )
        self._append_entry(end_entry)
        
        self._finalized = True
        
        # Calculate tape hash
        tape_hash = self.calculate_tape_hash()
        
        return {
            "run_id": self.run_id,
            "tape_path": str(self._tape_file) if self._tape_file else None,
            "message_count": message_count,
            "turn_count": len(turn_ids),
            "tape_hash": tape_hash,
            "entries": len(self._entries),
        }
    
    def calculate_tape_hash(self) -> str:
        """
        Calculate SHA256 hash of tape entries.
        
        Used for deterministic verification that two runs
        produce identical trajectories.
        
        Returns:
            Hex string of SHA256 hash
        """
        # Exclude run_start and run_end for hash
        # (they contain timestamps that vary)
        hashable_entries = [
            e for e in self._entries
            if e.type not in ("run_start", "run_end")
        ]
        
        # Create canonical JSON representation
        canonical = json.dumps(
            [e.to_dict() for e in hashable_entries],
            sort_keys=True,
            ensure_ascii=False
        )
        
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def get_entries(self) -> List[TapeEntry]:
        """Get all tape entries."""
        return list(self._entries)
    
    def get_tape_path(self) -> Optional[Path]:
        """Get the tape file path."""
        return self._tape_file


class TapeReplayer:
    """
    Replays conversation tape entries.
    
    Reads tape entries from a JSONL file and feeds them to
    the harness for deterministic replay testing.
    
    Usage:
        replayer = TapeReplayer(tape_path)
        entries = replayer.load()
        for entry in entries:
            if entry.type == "inbound":
                result = await harness.process_message(entry)
    """
    
    def __init__(self, tape_path: str):
        """
        Initialize tape replayer.
        
        Args:
            tape_path: Path to tape JSONL file
        """
        self.tape_path = Path(tape_path)
        self._entries: List[TapeEntry] = []
        self._loaded = False
    
    def load(self) -> List[TapeEntry]:
        """
        Load tape entries from file.
        
        Returns:
            List of TapeEntry objects
        """
        if self._loaded:
            return self._entries
        
        if not self.tape_path.exists():
            raise FileNotFoundError(f"Tape file not found: {self.tape_path}")
        
        self._entries = []
        with open(self.tape_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    self._entries.append(TapeEntry.from_dict(data))
        
        self._loaded = True
        return self._entries
    
    def get_entries_by_type(self, entry_type: str) -> List[TapeEntry]:
        """
        Get entries of a specific type.
        
        Args:
            entry_type: Type to filter by
            
        Returns:
            List of matching entries
        """
        if not self._loaded:
            self.load()
        
        return [e for e in self._entries if e.type == entry_type]
    
    def get_inbound_messages(self) -> List[TapeEntry]:
        """Get all inbound message entries."""
        return self.get_entries_by_type("inbound")
    
    def get_tool_calls(self) -> List[TapeEntry]:
        """Get all tool_call entries."""
        return self.get_entries_by_type("tool_call")
    
    def get_run_config(self) -> Optional[Dict[str, Any]]:
        """
        Get run configuration from run_start entry.
        
        Returns:
            Config dict or None if not found
        """
        run_starts = self.get_entries_by_type("run_start")
        if run_starts:
            return run_starts[0].config
        return None
    
    def calculate_tape_hash(self) -> str:
        """
        Calculate SHA256 hash of tape entries.
        
        Returns:
            Hex string of SHA256 hash
        """
        if not self._loaded:
            self.load()
        
        hashable_entries = [
            e for e in self._entries
            if e.type not in ("run_start", "run_end")
        ]
        
        canonical = json.dumps(
            [e.to_dict() for e in hashable_entries],
            sort_keys=True,
            ensure_ascii=False
        )
        
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    async def replay(
        self,
        harness: Optional[TestbotHarness] = None,
        dispatch: bool = True,
        on_entry: Optional[Callable[[TapeEntry, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Replay the tape through the harness.
        
        Args:
            harness: Optional harness instance (created from tape config if None)
            dispatch: Whether to dispatch to emotiond
            on_entry: Optional callback for each entry
            
        Returns:
            Dict with replay results including tape hash
        """
        if not self._loaded:
            self.load()
        
        # Get run config
        run_config = self.get_run_config()
        
        # Create harness if not provided
        if harness is None:
            config = TestbotConfig()
            if run_config:
                config = TestbotConfig(**run_config.get("config", {}))
            harness = TestbotHarness(config)
        
        results = []
        tool_results = []
        
        for entry in self._entries:
            result = None
            
            if entry.type == "inbound":
                # Create TestbotMessage from entry
                message = TestbotMessage(
                    message_id=entry.message_id or "",
                    sender_id=entry.sender_id or entry.sender or "user",
                    sender=entry.sender or "User",
                    text=entry.text or "",
                    ts=entry.ts,
                )
                
                if dispatch:
                    result = await harness.process_and_dispatch(message)
                else:
                    result = harness.process_message(message)
                
                results.append({
                    "entry_type": "inbound",
                    "turn_id": entry.turn_id,
                    "result": result,
                })
            
            elif entry.type == "tool_call":
                tool_results.append({
                    "entry_type": "tool_call",
                    "tool": entry.tool,
                    "args": entry.args,
                })
            
            elif entry.type == "tool_return":
                if tool_results:
                    last_call = tool_results[-1]
                    last_call["result"] = entry.result
            
            # Call optional callback
            if on_entry and result:
                await on_entry(entry, result)
        
        # Finalize harness
        harness_summary = harness.finalize()
        
        return {
            "tape_hash": self.calculate_tape_hash(),
            "harness_hash": harness_summary.get("tape_hash"),
            "entries_processed": len(self._entries),
            "results_count": len(results),
            "results": results,
            "harness_summary": harness_summary,
        }
    
    def verify_hash(self, expected_hash: str) -> Dict[str, Any]:
        """
        Verify tape hash matches expected value.
        
        Args:
            expected_hash: Expected SHA256 hash
            
        Returns:
            Dict with match status and both hashes
        """
        actual_hash = self.calculate_tape_hash()
        
        return {
            "match": actual_hash == expected_hash,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }


def load_tape(tape_path: str) -> List[TapeEntry]:
    """
    Convenience function to load tape entries.
    
    Args:
        tape_path: Path to tape JSONL file
        
    Returns:
        List of TapeEntry objects
    """
    replayer = TapeReplayer(tape_path)
    return replayer.load()


def calculate_tape_hash_from_file(tape_path: str) -> str:
    """
    Calculate hash of tape file directly.
    
    Args:
        tape_path: Path to tape JSONL file
        
    Returns:
        Hex string of SHA256 hash
    """
    replayer = TapeReplayer(tape_path)
    return replayer.calculate_tape_hash()


async def record_conversation(
    messages: List[TestbotMessage],
    config: Optional[TestbotConfig] = None,
    dispatch: bool = True,
) -> Dict[str, Any]:
    """
    Record a conversation to tape.
    
    Convenience function that creates a recorder and harness,
    processes all messages, and returns the tape summary.
    
    Args:
        messages: List of testbot messages
        config: Optional harness configuration
        dispatch: Whether to dispatch to emotiond
        
    Returns:
        Dict with tape summary and results
    """
    config = config or TestbotConfig()
    harness = TestbotHarness(config)
    recorder = TapeRecorder(config)
    
    recorder.start()
    results = []
    
    for message in messages:
        if dispatch:
            result = await harness.process_and_dispatch(message)
        else:
            result = harness.process_message(message)
        
        # Record to tape
        recorder.record_inbound(message, result["turn_id"])
        
        if "process_result" in result:
            recorder.record_tool_call(
                "process_event",
                {
                    "type": "user_message",
                    "actor": message.sender,
                    "text": message.text,
                },
                result["turn_id"],
            )
            recorder.record_tool_return(
                result["process_result"],
                result["turn_id"],
            )
        
        results.append(result)
    
    tape_summary = recorder.finalize()
    harness_summary = harness.finalize()
    
    return {
        "tape": tape_summary,
        "harness": harness_summary,
        "results": results,
    }
