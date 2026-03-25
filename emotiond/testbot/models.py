"""
Pydantic models for testbot harness.

Defines message formats, conversation context, and configuration
for E2E testing of emotiond.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
import time


class TestbotMessage(BaseModel):
    """
    Input message from testbot.
    
    Represents a single message in a test conversation,
    originating from an external test driver.
    """
    message_id: str = Field(..., description="Unique message identifier")
    sender_id: str = Field(..., description="ID of the message sender")
    sender: str = Field(..., description="Display name of sender")
    text: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Human-readable timestamp")
    ts: Optional[float] = Field(default_factory=time.time, description="Unix timestamp")
    
    # Optional metadata for richer context
    sentiment: Optional[str] = Field(None, description="positive|negative|neutral")
    intent: Optional[str] = Field(None, description="Message intent hint")


class TestbotConfig(BaseModel):
    """
    Configuration for testbot harness.
    
    Controls channel isolation, output paths, and behavior.
    """
    model_config = ConfigDict(extra="allow")
    
    channel: str = Field(default="testbot", description="Channel identifier for isolation")
    thread_id: str = Field(default="test_001", description="Thread ID for conversation isolation")
    output_dir: str = Field(default="artifacts/testbot/tapes", description="Directory for run.jsonl output")
    run_id: Optional[str] = Field(None, description="Unique run identifier (auto-generated if None)")
    log_to_file: bool = Field(default=True, description="Whether to write events to run.jsonl")


class ConversationContext(BaseModel):
    """
    Runtime context for a single conversation.
    
    Tracks turn count, message history, and derived IDs.
    """
    turn_id: int = Field(default=0, description="Current turn number (1-indexed)")
    channel: str = Field(default="testbot", description="Channel identifier")
    thread_id: str = Field(default="test_001", description="Thread identifier")
    start_ts: float = Field(default_factory=time.time, description="Conversation start timestamp")
    message_count: int = Field(default=0, description="Total messages processed")
    
    # Track conversation participants
    participants: Dict[str, str] = Field(
        default_factory=lambda: {"agent": "agent"},
        description="Map of role -> participant_id"
    )
    
    def next_turn(self) -> int:
        """Advance to next turn and return new turn_id."""
        self.turn_id += 1
        return self.turn_id
    
    def increment_message(self) -> int:
        """Increment message count and return new count."""
        self.message_count += 1
        return self.message_count


class ConversationTapeEntry(BaseModel):
    """
    Single entry in conversation tape (JSONL format).
    
    Captures inbound/outbound messages, tool calls, and results
    for deterministic replay.
    """
    type: str = Field(..., description="inbound|outbound|tool_call|tool_return")
    ts: float = Field(default_factory=time.time, description="Unix timestamp")
    message_id: Optional[str] = Field(None, description="Message ID if applicable")
    sender: Optional[str] = Field(None, description="Sender name for messages")
    text: Optional[str] = Field(None, description="Message text")
    turn_id: Optional[int] = Field(None, description="Turn number")
    channel: Optional[str] = Field(None, description="Channel identifier")
    thread_id: Optional[str] = Field(None, description="Thread identifier")
    tool: Optional[str] = Field(None, description="Tool name for tool_call/tool_return")
    args: Optional[Dict[str, Any]] = Field(None, description="Tool arguments")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool result")


class ScenarioMessage(BaseModel):
    """
    Message in a test scenario.
    
    Used for defining test scenarios in JSON files.
    """
    sender: str = Field(..., description="user|agent")
    text: str = Field(..., description="Message content")
    sentiment: Optional[str] = Field(None, description="Expected sentiment")
    expected_action: Optional[str] = Field(None, description="Expected agent action")


class Scenario(BaseModel):
    """
    Test scenario definition.
    
    Defines a conversation for replay testing.
    """
    name: str = Field(..., description="Scenario name")
    description: Optional[str] = Field(None, description="Scenario description")
    messages: List[ScenarioMessage] = Field(default_factory=list, description="Conversation messages")
    config: Optional[TestbotConfig] = Field(None, description="Optional harness config")
