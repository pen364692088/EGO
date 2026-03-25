"""
Testbot Harness - E2E conversation testing infrastructure.

Provides message-to-event conversion for testbot conversations,
enabling recording, replay, and deterministic testing of emotiond.
"""
from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    ConversationContext,
)
from emotiond.testbot.harness import (
    TestbotHarness,
    process_testbot_message,
)
from emotiond.testbot.tape import (
    TapeRecorder,
    TapeReplayer,
    TapeEntry,
    load_tape,
    calculate_tape_hash_from_file,
    record_conversation,
)

__all__ = [
    "TestbotMessage",
    "TestbotConfig", 
    "ConversationContext",
    "TestbotHarness",
    "process_testbot_message",
    # Tape recording/replay
    "TapeRecorder",
    "TapeReplayer",
    "TapeEntry",
    "load_tape",
    "calculate_tape_hash_from_file",
    "record_conversation",
]
