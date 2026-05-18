#!/usr/bin/env python3
"""
Run testbot conversation from scenario file.

Usage:
    python scripts/run_testbot_conversation.py --scenario tests/testbot/scenarios/simple.json
    python scripts/run_testbot_conversation.py --messages '[
        {"message_id": "1", "sender_id": "user1", "sender": "User", "text": "Hello"}
    ]'
    
Options:
    --scenario PATH    Path to scenario JSON file
    --messages JSON    Inline JSON array of messages
    --channel NAME     Channel identifier (default: testbot)
    --thread-id ID     Thread identifier (default: test_001)
    --output-dir DIR   Output directory for tapes (default: artifacts/testbot/tapes)
    --no-dispatch      Don't dispatch events to emotiond (dry run)
    --format FMT       Output format: json|summary (default: summary)
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    Scenario,
)
from emotiond.testbot.harness import (
    TestbotHarness,
    run_conversation,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run testbot conversation from scenario or inline messages"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Path to scenario JSON file"
    )
    parser.add_argument(
        "--messages",
        type=str,
        help="Inline JSON array of messages"
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="testbot",
        help="Channel identifier (default: testbot)"
    )
    parser.add_argument(
        "--thread-id",
        type=str,
        default="test_001",
        help="Thread identifier (default: test_001)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/testbot/tapes",
        help="Output directory for tapes"
    )
    parser.add_argument(
        "--no-dispatch",
        action="store_true",
        help="Don't dispatch events to emotiond (dry run)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "summary"],
        default="summary",
        help="Output format (default: summary)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        help="Custom run identifier"
    )
    
    return parser.parse_args()


def load_scenario(path: str) -> Scenario:
    """Load scenario from JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return Scenario(**data)


def messages_from_scenario(scenario: Scenario) -> List[TestbotMessage]:
    """Convert scenario messages to TestbotMessages."""
    messages = []
    for i, msg in enumerate(scenario.messages):
        # Only include user messages (agent messages are expected responses)
        if msg.sender == "user":
            messages.append(TestbotMessage(
                message_id=f"msg_{i+1}",
                sender_id="user",
                sender="User",
                text=msg.text,
            ))
    return messages


def messages_from_json(json_str: str) -> List[TestbotMessage]:
    """Parse messages from inline JSON."""
    data = json.loads(json_str)
    return [TestbotMessage(**msg) for msg in data]


def format_summary(result: Dict[str, Any]) -> str:
    """Format result as human-readable summary."""
    lines = [
        "=== Testbot Conversation Summary ===",
        f"Run ID:        {result.get('run_id', 'N/A')}",
        f"Tape Path:     {result.get('tape_path', 'N/A')}",
        f"Messages:      {result.get('message_count', 0)}",
        f"Turns:         {result.get('turn_count', 0)}",
        f"Tape Hash:     {result.get('tape_hash', 'N/A')[:16]}...",
        "",
    ]
    
    if "results" in result:
        lines.append("=== Per-Message Results ===")
        for i, r in enumerate(result["results"], 1):
            lines.append(f"  [{i}] Turn {r.get('turn_id', '?')}: {r.get('message_id', '?')}")
            if "process_result" in r:
                pr = r["process_result"]
                status = pr.get("status", "unknown")
                lines.append(f"      Status: {status}")
    
    return "\n".join(lines)


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Load messages
    messages: List[TestbotMessage] = []
    
    if args.scenario:
        scenario = load_scenario(args.scenario)
        messages = messages_from_scenario(scenario)
        print(f"Loaded {len(messages)} messages from scenario: {scenario.name}")
    elif args.messages:
        messages = messages_from_json(args.messages)
        print(f"Loaded {len(messages)} inline messages")
    else:
        print("Error: Must specify --scenario or --messages", file=sys.stderr)
        return 1
    
    if not messages:
        print("Error: No messages to process", file=sys.stderr)
        return 1
    
    # Create config
    config = TestbotConfig(
        channel=args.channel,
        thread_id=args.thread_id,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )
    
    # Run conversation
    dispatch = not args.no_dispatch
    result = await run_conversation(messages, config, dispatch=dispatch)
    
    # Output result
    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_summary(result))
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
