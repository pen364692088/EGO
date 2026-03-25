#!/usr/bin/env python3
"""
Replay Conversation Tape - CLI entry point for deterministic replay.

Usage:
    python scripts/replay_conversation_tape.py <tape_path> [--hash <expected_hash>] [--no-dispatch] [--verbose]
    
Examples:
    # Basic replay
    python scripts/replay_conversation_tape.py artifacts/testbot/tapes/tape_20260305.jsonl
    
    # Verify hash
    python scripts/replay_conversation_tape.py tape.jsonl --hash abc123...
    
    # Dry run (no emotiond dispatch)
    python scripts/replay_conversation_tape.py tape.jsonl --no-dispatch
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.testbot.tape import TapeReplayer, TapeEntry, calculate_tape_hash_from_file
from emotiond.testbot.harness import TestbotHarness
from emotiond.testbot.models import TestbotConfig


def print_entry(entry: TapeEntry, verbose: bool = False):
    """Print a tape entry."""
    type_str = entry.type.upper().ljust(12)
    
    if entry.type == "inbound":
        print(f"  [{type_str}] turn={entry.turn_id} sender={entry.sender} text={entry.text[:50]}...")
    elif entry.type == "outbound":
        print(f"  [{type_str}] turn={entry.turn_id} text={entry.text[:50]}...")
    elif entry.type == "tool_call":
        print(f"  [{type_str}] turn={entry.turn_id} tool={entry.tool}")
        if verbose and entry.args:
            print(f"              args={json.dumps(entry.args, indent=14)}")
    elif entry.type == "tool_return":
        print(f"  [{type_str}] turn={entry.turn_id}")
        if verbose and entry.result:
            # Print summary, not full result
            result_keys = list(entry.result.keys())[:5]
            print(f"              result_keys={result_keys}...")
    elif entry.type == "run_start":
        print(f"  [{type_str}] run_id={entry.run_id}")
        if verbose:
            print(f"              channel={entry.channel} thread_id={entry.thread_id}")
    elif entry.type == "run_end":
        print(f"  [{type_str}] messages={entry.message_count} turns={entry.turn_count}")


async def replay_tape(
    tape_path: str,
    expected_hash: str = None,
    dispatch: bool = True,
    verbose: bool = False,
) -> int:
    """
    Replay a conversation tape.
    
    Args:
        tape_path: Path to tape JSONL file
        expected_hash: Expected SHA256 hash (optional)
        dispatch: Whether to dispatch to emotiond
        verbose: Verbose output
        
    Returns:
        Exit code (0 for success, 1 for hash mismatch, 2 for errors)
    """
    print(f"Loading tape: {tape_path}")
    
    try:
        replayer = TapeReplayer(tape_path)
        entries = replayer.load()
    except FileNotFoundError:
        print(f"ERROR: Tape file not found: {tape_path}")
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in tape file: {e}")
        return 2
    except Exception as e:
        print(f"ERROR: Failed to load tape: {e}")
        return 2
    
    print(f"Loaded {len(entries)} entries")
    
    # Calculate and print hash
    actual_hash = replayer.calculate_tape_hash()
    print(f"Tape hash: {actual_hash}")
    
    # Verify hash if provided
    if expected_hash:
        print(f"Expected:  {expected_hash}")
        if actual_hash != expected_hash:
            print("ERROR: Hash mismatch!")
            print("  This indicates the tape has been modified or corrupted.")
            return 1
        print("Hash verified OK")
    
    # Print entries
    print("\nTape entries:")
    for entry in entries:
        print_entry(entry, verbose)
    
    # Get run config
    run_config = replayer.get_run_config()
    if run_config:
        print(f"\nRun config: channel={run_config.get('channel')} thread_id={run_config.get('thread_id')}")
    
    # Replay through harness
    print(f"\nReplaying (dispatch={dispatch})...")
    
    try:
        # Create harness from config
        config = TestbotConfig()
        if run_config and run_config.get("config"):
            config_dict = run_config["config"]
            config = TestbotConfig(
                channel=config_dict.get("channel", "testbot"),
                thread_id=config_dict.get("thread_id", "test_001"),
                output_dir=config_dict.get("output_dir", "artifacts/testbot/tapes"),
                log_to_file=config_dict.get("log_to_file", True),
            )
        
        harness = TestbotHarness(config)
        
        # Replay each inbound message
        inbound_entries = replayer.get_inbound_messages()
        results = []
        
        for entry in inbound_entries:
            from emotiond.testbot.models import TestbotMessage
            
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
                "turn_id": entry.turn_id,
                "message_id": entry.message_id,
                "valence": result.get("process_result", {}).get("valence") if dispatch else None,
            })
            
            if verbose:
                print(f"  Turn {entry.turn_id}: {entry.text[:30]}...")
        
        # Finalize
        harness_summary = harness.finalize()
        
        print(f"\nReplay complete:")
        print(f"  Messages processed: {len(inbound_entries)}")
        print(f"  Harness hash: {harness_summary.get('tape_hash', 'N/A')}")
        
        # Print results summary
        if verbose and results:
            print("\nResults:")
            for r in results:
                valence_str = f"valence={r['valence']:.3f}" if r['valence'] is not None else "no dispatch"
                print(f"  Turn {r['turn_id']}: {valence_str}")
        
        return 0
        
    except Exception as e:
        print(f"ERROR: Replay failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 2


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Replay conversation tape for deterministic testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic replay
  python scripts/replay_conversation_tape.py tape.jsonl
  
  # Verify hash for deterministic validation
  python scripts/replay_conversation_tape.py tape.jsonl --hash abc123def456...
  
  # Dry run without emotiond dispatch
  python scripts/replay_conversation_tape.py tape.jsonl --no-dispatch
  
  # Verbose output
  python scripts/replay_conversation_tape.py tape.jsonl -v
        """
    )
    
    parser.add_argument(
        "tape_path",
        help="Path to tape JSONL file"
    )
    
    parser.add_argument(
        "--hash",
        dest="expected_hash",
        help="Expected SHA256 hash for deterministic verification"
    )
    
    parser.add_argument(
        "--no-dispatch",
        action="store_true",
        help="Do not dispatch to emotiond (dry run)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(replay_tape(
        tape_path=args.tape_path,
        expected_hash=args.expected_hash,
        dispatch=not args.no_dispatch,
        verbose=args.verbose,
    ))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
