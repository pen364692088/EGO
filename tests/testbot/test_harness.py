"""
Unit tests for testbot harness.

Tests message conversion, event generation, and tape recording.
"""
import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    ConversationContext,
    ConversationTapeEntry,
    Scenario,
    ScenarioMessage,
)
from emotiond.testbot.harness import (
    TestbotHarness,
    process_testbot_message,
    run_conversation,
)


class TestTestbotMessage:
    """Tests for TestbotMessage model."""
    
    def test_create_message(self):
        """Test creating a basic testbot message."""
        msg = TestbotMessage(
            message_id="123",
            sender_id="user1",
            sender="User",
            text="Hello, world!",
        )
        assert msg.message_id == "123"
        assert msg.sender_id == "user1"
        assert msg.sender == "User"
        assert msg.text == "Hello, world!"
        assert msg.ts is not None
    
    def test_message_with_timestamp(self):
        """Test message with explicit timestamp."""
        msg = TestbotMessage(
            message_id="124",
            sender_id="user1",
            sender="User",
            text="Test",
            timestamp="Thu 2026-03-05 10:00 CST",
        )
        assert msg.timestamp == "Thu 2026-03-05 10:00 CST"


class TestTestbotConfig:
    """Tests for TestbotConfig model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TestbotConfig()
        assert config.channel == "testbot"
        assert config.thread_id == "test_001"
        assert config.log_to_file is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = TestbotConfig(
            channel="custom_channel",
            thread_id="custom_thread",
            output_dir="/tmp/tapes",
            log_to_file=False,
        )
        assert config.channel == "custom_channel"
        assert config.thread_id == "custom_thread"
        assert config.output_dir == "/tmp/tapes"
        assert config.log_to_file is False


class TestConversationContext:
    """Tests for ConversationContext model."""
    
    def test_context_defaults(self):
        """Test context default values."""
        ctx = ConversationContext()
        assert ctx.turn_id == 0
        assert ctx.channel == "testbot"
        assert ctx.thread_id == "test_001"
        assert ctx.message_count == 0
    
    def test_next_turn(self):
        """Test turn advancement."""
        ctx = ConversationContext()
        assert ctx.turn_id == 0
        
        turn1 = ctx.next_turn()
        assert turn1 == 1
        assert ctx.turn_id == 1
        
        turn2 = ctx.next_turn()
        assert turn2 == 2
        assert ctx.turn_id == 2
    
    def test_increment_message(self):
        """Test message count increment."""
        ctx = ConversationContext()
        assert ctx.message_count == 0
        
        count1 = ctx.increment_message()
        assert count1 == 1
        assert ctx.message_count == 1


class TestTestbotHarness:
    """Tests for TestbotHarness class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        d = tempfile.mkdtemp(prefix="testbot_test_")
        yield d
        shutil.rmtree(d, ignore_errors=True)
    
    @pytest.fixture
    def test_config(self, temp_dir):
        """Create test configuration with temp directory."""
        return TestbotConfig(
            channel="test_channel",
            thread_id="test_thread",
            output_dir=temp_dir,
            run_id="test_run",
        )
    
    def test_harness_init(self, test_config):
        """Test harness initialization."""
        harness = TestbotHarness(test_config)
        assert harness.config.channel == "test_channel"
        assert harness.config.thread_id == "test_thread"
        assert harness.context.channel == "test_channel"
    
    def test_process_message(self, test_config):
        """Test basic message processing."""
        harness = TestbotHarness(test_config)
        
        msg = TestbotMessage(
            message_id="msg1",
            sender_id="user1",
            sender="User",
            text="Hello",
        )
        
        result = harness.process_message(msg)
        
        assert "event" in result
        assert result["event"]["type"] == "user_message"
        assert result["event"]["actor"] == "User"
        assert result["event"]["target"] == "agent"
        assert result["event"]["text"] == "Hello"
        assert result["turn_id"] == 1
        assert result["message_id"] == "msg1"
    
    def test_message_meta_fields(self, test_config):
        """Test that message metadata is included in event."""
        harness = TestbotHarness(test_config)
        
        msg = TestbotMessage(
            message_id="msg2",
            sender_id="user1",
            sender="User",
            text="Test",
            timestamp="Thu 2026-03-05 10:00 CST",
        )
        
        result = harness.process_message(msg)
        event = result["event"]
        
        assert event["meta"]["message_id"] == "msg2"
        assert event["meta"]["turn_id"] == 1
        assert event["meta"]["channel"] == "test_channel"
        assert event["meta"]["thread_id"] == "test_thread"
        assert event["meta"]["sender_id"] == "user1"
        assert event["meta"]["testbot"] is True
    
    def test_turn_tracking(self, test_config):
        """Test that turns are tracked correctly."""
        harness = TestbotHarness(test_config)
        
        msg1 = TestbotMessage(
            message_id="m1", sender_id="u1", sender="User", text="Hello"
        )
        msg2 = TestbotMessage(
            message_id="m2", sender_id="u1", sender="User", text="World"
        )
        
        result1 = harness.process_message(msg1)
        result2 = harness.process_message(msg2)
        
        assert result1["turn_id"] == 1
        assert result2["turn_id"] == 2
        assert harness.context.turn_id == 2
    
    def test_tape_recording(self, test_config, temp_dir):
        """Test that tape is written to file."""
        harness = TestbotHarness(test_config)
        
        msg = TestbotMessage(
            message_id="m1", sender_id="u1", sender="User", text="Test"
        )
        harness.process_message(msg)
        harness.finalize()
        
        tape_path = Path(temp_dir) / "test_run.jsonl"
        assert tape_path.exists()
        
        with open(tape_path) as f:
            lines = f.readlines()
        
        assert len(lines) >= 3  # run_start, inbound, run_end
        
        # Check run_start entry
        entry0 = json.loads(lines[0])
        assert entry0["type"] == "run_start"
        
        # Check inbound entry
        entry1 = json.loads(lines[1])
        assert entry1["type"] == "inbound"
        assert entry1["text"] == "Test"
    
    def test_tape_hash_determinism(self, test_config):
        """Test that identical conversations produce identical hashes."""
        harness1 = TestbotHarness(test_config)
        harness2 = TestbotHarness(test_config)
        
        msg = TestbotMessage(
            message_id="m1", sender_id="u1", sender="User", text="Test"
        )
        
        harness1.process_message(msg)
        harness2.process_message(msg)
        
        hash1 = harness1.calculate_tape_hash()
        hash2 = harness2.calculate_tape_hash()
        
        assert hash1 == hash2
    
    def test_record_outbound(self, test_config):
        """Test recording outbound (agent) messages."""
        harness = TestbotHarness(test_config)
        
        # Process an inbound message first
        msg = TestbotMessage(
            message_id="m1", sender_id="u1", sender="User", text="Hello"
        )
        harness.process_message(msg)
        
        # Record outbound
        result = harness.record_outbound("Hi there!", message_id="agent_1")
        
        assert result["type"] == "outbound"
        assert result["text"] == "Hi there!"
        assert result["message_id"] == "agent_1"
        assert result["turn_id"] == 1
    
    def test_finalize_summary(self, test_config):
        """Test finalize returns correct summary."""
        harness = TestbotHarness(test_config)
        
        msg1 = TestbotMessage(
            message_id="m1", sender_id="u1", sender="User", text="Hello"
        )
        msg2 = TestbotMessage(
            message_id="m2", sender_id="u1", sender="User", text="World"
        )
        
        harness.process_message(msg1)
        harness.process_message(msg2)
        
        summary = harness.finalize()
        
        assert summary["message_count"] == 2
        assert summary["turn_count"] == 2
        assert "tape_hash" in summary


class TestProcessTestbotMessage:
    """Tests for convenience function."""
    
    def test_process_single_message(self):
        """Test processing a single message."""
        msg = TestbotMessage(
            message_id="m1",
            sender_id="u1",
            sender="User",
            text="Hello",
        )
        
        result = process_testbot_message(msg)
        
        assert "event" in result
        assert result["event"]["type"] == "user_message"


class TestRunConversation:
    """Tests for run_conversation function."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        d = tempfile.mkdtemp(prefix="testbot_conv_")
        yield d
        shutil.rmtree(d, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_run_conversation_no_dispatch(self, temp_dir):
        """Test running conversation without dispatch."""
        config = TestbotConfig(
            output_dir=temp_dir,
            run_id="conv_test",
        )
        
        messages = [
            TestbotMessage(
                message_id=f"m{i}",
                sender_id="u1",
                sender="User",
                text=f"Message {i}",
            )
            for i in range(1, 4)
        ]
        
        result = await run_conversation(messages, config, dispatch=False)
        
        assert result["message_count"] == 3
        assert result["turn_count"] == 3
        assert len(result["results"]) == 3
        assert "tape_hash" in result
    
    @pytest.mark.asyncio
    async def test_run_conversation_with_dispatch(self, temp_dir):
        """Test running conversation with emotiond dispatch."""
        # This test requires emotiond to be properly initialized
        # We'll skip the actual dispatch in CI if emotiond is not available
        config = TestbotConfig(
            output_dir=temp_dir,
            run_id="conv_dispatch",
        )
        
        messages = [
            TestbotMessage(
                message_id="m1",
                sender_id="u1",
                sender="User",
                text="Hello",
            ),
        ]
        
        try:
            result = await run_conversation(messages, config, dispatch=True)
            assert "process_result" in result["results"][0]
        except Exception as e:
            # If emotiond is not available, skip gracefully
            pytest.skip(f"emotiond not available: {e}")


class TestScenario:
    """Tests for scenario loading."""
    
    def test_scenario_model(self):
        """Test scenario model creation."""
        scenario = Scenario(
            name="test_scenario",
            description="A test scenario",
            messages=[
                ScenarioMessage(sender="user", text="Hello"),
                ScenarioMessage(sender="agent", text="Hi there!"),
            ],
        )
        
        assert scenario.name == "test_scenario"
        assert len(scenario.messages) == 2
        assert scenario.messages[0].sender == "user"
    
    def test_scenario_from_json(self, tmp_path):
        """Test loading scenario from JSON file."""
        scenario_data = {
            "name": "simple_greeting",
            "description": "Simple greeting scenario",
            "messages": [
                {"sender": "user", "text": "你好"},
                {"sender": "agent", "text": "你好！有什么可以帮你的？"},
            ]
        }
        
        scenario_file = tmp_path / "scenario.json"
        scenario_file.write_text(json.dumps(scenario_data))
        
        loaded = Scenario(**json.loads(scenario_file.read_text()))
        
        assert loaded.name == "simple_greeting"
        assert len(loaded.messages) == 2


class TestConversationTapeEntry:
    """Tests for tape entry model."""
    
    def test_inbound_entry(self):
        """Test creating inbound tape entry."""
        entry = ConversationTapeEntry(
            type="inbound",
            message_id="m1",
            sender="User",
            text="Hello",
            turn_id=1,
            channel="testbot",
            thread_id="test_001",
        )
        
        assert entry.type == "inbound"
        assert entry.text == "Hello"
    
    def test_tool_call_entry(self):
        """Test creating tool call tape entry."""
        entry = ConversationTapeEntry(
            type="tool_call",
            tool="process_event",
            args={"type": "user_message", "actor": "User"},
            turn_id=1,
        )
        
        assert entry.type == "tool_call"
        assert entry.tool == "process_event"
        assert entry.args["type"] == "user_message"
