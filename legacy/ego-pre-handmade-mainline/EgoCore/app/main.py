"""
OpenEmotion Agent Runtime - Main Entry Point

This is the main entry point for the OpenEmotion Agent Runtime.
It initializes all components and starts the runtime.

Usage:
    python -m app.main              # Show status and exit
    python -m app.main --telegram   # Start Telegram bot
    python -m app.main --status     # Show status only
    python -m app.main --dashboard  # Start read-only dashboard
    python -m app.main --restore --telegram  # Run explicit restore before Telegram startup
"""

import os
import socket
import tempfile
import argparse
import sys
from pathlib import Path

from app.config import load_config, get_config, ConfigError
from app.live_process_version import write_live_process_version_report
from app.logger import init_logging, get_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenEmotion Agent Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--telegram", "-t",
        action="store_true",
        help="Start Telegram bot"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show status only (no bot startup)"
    )
    parser.add_argument(
        "--runtime-v2-cli",
        action="store_true",
        help="Run Runtime v2 interactive CLI loop"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Run read-only Growth Dashboard v1"
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Run explicit restore before Telegram startup"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Dashboard bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8787,
        help="Dashboard bind port (default: 8787)"
    )
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> str | None:
    if not args.restore:
        return None
    if not args.telegram:
        return "--restore 只能与 --telegram 一起使用。"
    if args.dashboard:
        return "--restore 不能与 --dashboard 一起使用。"
    if args.status:
        return "--restore 不能与 --status 一起使用。"
    if args.runtime_v2_cli:
        return "--restore 不能与 --runtime-v2-cli 一起使用。"
    return None


def show_status(config, logger) -> None:
    """Show configuration and status summary."""
    # Print configuration summary
    print("\n" + "=" * 40)
    print("Configuration Summary:")
    print("-" * 40)
    print(f"  App Name: {config.app.get('name')}")
    print(f"  Environment: {config.app.get('environment', 'development')}")
    print(f"  Log Level: {config.get('app.logging.level', 'INFO')}")
    print(f"  Default LLM Provider: {config.llm.get('default_provider')}")
    print(f"  Default LLM Model: {config.llm.get('default_model')}")
    print(f"  Telegram Enabled: {config.telegram.get('enabled', False)}")
    print(f"  Memory Enabled: {config.memory.get('global', {}).get('enabled', True)}")
    print(f"  OpenEmotion Bridge Enabled: {config.openemotion.get('enabled', False)}")

    # Check for API keys
    print("\nAPI Keys Status:")
    print("-" * 40)

    telegram_token = config.get_env('TELEGRAM_BOT_TOKEN')
    print(f"  TELEGRAM_BOT_TOKEN: {'✓ Set' if telegram_token else '✗ Not set'}")

    qianfan_key = config.get_env('QIANFAN_API_KEY')
    print(f"  QIANFAN_API_KEY: {'✓ Set' if qianfan_key else '✗ Not set'}")

    openrouter_key = config.get_env('OPENROUTER_API_KEY')
    print(f"  OPENROUTER_API_KEY: {'✓ Set' if openrouter_key else '✗ Not set'}")

    openai_key = config.get_env('OPENAI_API_KEY')
    print(f"  OPENAI_API_KEY: {'✓ Set' if openai_key else '✗ Not set'}")

    anthropic_key = config.get_env('ANTHROPIC_API_KEY')
    print(f"  ANTHROPIC_API_KEY: {'✓ Set' if anthropic_key else '✗ Not set'}")

    deepseek_key = config.get_env('DEEPSEEK_API_KEY')
    print(f"  DEEPSEEK_API_KEY: {'✓ Set' if deepseek_key else '✗ Not set'}")

    print("\n" + "=" * 40)


def main() -> int:
    """
    Main entry point for OpenEmotion Agent Runtime.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # =========================================================================
    # Gate R0: Canonical Repo Guard (MANDATORY)
    # Must be the FIRST check before any other operations
    # =========================================================================
    import sys
    from pathlib import Path
    
    try:
        # Import repo guard
        repo_guard_path = Path(__file__).parent.parent / "tools" / "repo-root-guard"
        if repo_guard_path.exists():
            import subprocess
            
            # Run repo guard as subprocess (more reliable)
            result = subprocess.run(
                [sys.executable, str(repo_guard_path), "--check", "--json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # Wrong repo - BLOCK
                import json
                try:
                    guard_data = json.loads(result.stdout) if result.stdout.strip() else {}
                    print(guard_data.get("message", "🚫 REPO ROOT MISMATCH"), file=sys.stderr)
                except:
                    print(result.stdout, file=sys.stderr)
                return 2
    except subprocess.TimeoutExpired:
        print("⚠️ Repo guard timeout, continuing...", file=sys.stderr)
    except Exception as e:
        # If repo guard fails, warn but continue (graceful degradation)
        print(f"⚠️ Repo guard check failed: {e}", file=sys.stderr)
    # =========================================================================
    
    args = parse_args()
    args_error = _validate_args(args)
    if args_error:
        print(f"\n❌ Argument Error: {args_error}", file=sys.stderr)
        return 2

    print("OpenEmotion Agent Runtime v0.1.0")
    print("=" * 40)

    try:
        # Step 1: Load configuration
        print("\n[1/3] Loading configuration...")
        config = load_config()
        print("  ✓ Configuration loaded successfully")

        # Step 2: Initialize logging
        print("\n[2/3] Initializing logging...")
        log_config = config.get('app.logging', {})
        log_config['name'] = config.app.get('name', 'openemotion')
        init_logging(log_config)
        logger = get_logger('main')
        print("  ✓ Logging initialized")

        # Step 3: Verify runtime components
        print("\n[3/3] Verifying runtime components...")

        # Check paths
        data_dir = config.get_path('data_dir')
        checkpoint_dir = config.get_path('checkpoint_dir')
        memory_dir = config.get_path('memory_dir')
        events_dir = config.get_path('events_dir')

        print(f"  Data directory: {data_dir}")
        print(f"  Checkpoint directory: {checkpoint_dir}")
        print(f"  Memory directory: {memory_dir}")
        print(f"  Events directory: {events_dir}")

        # Create directories if needed
        for dir_path in [data_dir, checkpoint_dir, memory_dir, events_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        print("  ✓ Runtime directories verified")

        # Proto-Self Kernel: Explicit evidence on startup
        print("\n" + "-" * 40)
        print("Proto-Self Kernel Status:")
        print("-" * 40)
        proto_self_enabled = config.openemotion.get('enabled', False)
        print(f"  PROTO_SELF_ENABLED={proto_self_enabled}")

        if proto_self_enabled:
            # Check if adapter can be imported
            try:
                from app.openemotion_adapter import ProtoSelfAdapter, ProtoSelfTraceBridge
                print("  PROTO_SELF_ADAPTER_LOADED=true")

                # Proto-Self paths
                mirror_dir = Path("artifacts/proto_self_mirror")
                trace_path = Path("logs/proto_self_trace.jsonl")
                print(f"  PROTO_SELF_MIRROR_PATH={mirror_dir.absolute()}")
                print(f"  PROTO_SELF_TRACE_PATH={trace_path.absolute()}")

                # Check writability
                mirror_dir.mkdir(parents=True, exist_ok=True)
                Path("logs").mkdir(parents=True, exist_ok=True)
                mirror_writable = os.access(mirror_dir, os.W_OK)
                trace_writable = os.access(Path("logs"), os.W_OK)
                print(f"  PROTO_SELF_MIRROR_WRITABLE={mirror_writable}")
                print(f"  PROTO_SELF_TRACE_WRITABLE={trace_writable}")

                if mirror_writable and trace_writable:
                    print("  ✓ Proto-Self Kernel: READY")
                else:
                    print("  ⚠ Proto-Self Kernel: PATHS NOT WRITABLE")
            except ImportError as e:
                print(f"  PROTO_SELF_ADAPTER_LOADED=false")
                print(f"  PROTO_SELF_ERROR=ImportError: {e}")
                print("  ✗ Proto-Self Kernel: ADAPTER NOT AVAILABLE")
        else:
            print("  PROTO_SELF_ADAPTER_LOADED=not_attempted")
            print("  ✗ Proto-Self Kernel: DISABLED in config")
        print("-" * 40)

        # Show status
        show_status(config, logger)

        pending_restore_observation = None
        if args.restore:
            print("\n" + "=" * 40)
            print("Running Explicit Restore...")
            print("=" * 40)
            from app.restore_runtime import format_restore_summary, perform_startup_restore

            restore_result, pending_restore_observation = perform_startup_restore(
                artifacts_dir=Path("artifacts"),
                audit_dir=Path("artifacts") / "restore" / "audit",
                session_id="telegram_startup_restore",
            )
            summary = format_restore_summary(pending_restore_observation)
            print(f"  {summary}")
            logger.info("restore.startup %s", summary)
            if restore_result.status == "failed":
                print("  ✗ Explicit restore failed; refusing Telegram startup")
                return 1
            print("  ✓ Explicit restore completed; pending observation attached to first post-restore turn")

        # Start Runtime v2 CLI if requested
        if args.runtime_v2_cli:
            print("\n" + "=" * 40)
            print("Starting Runtime v2 CLI...")
            print("=" * 40)
            from app.runtime_v2 import run_cli
            return run_cli()

        if args.dashboard:
            print("\n" + "=" * 40)
            print("Starting Growth Dashboard v1...")
            print("=" * 40)
            from app.dashboard import run_dashboard_server

            run_dashboard_server(host=args.host, port=args.port)
            return 0

        # Start Telegram bot if requested
        if args.telegram:
            print("\n" + "=" * 40)
            print("Starting Telegram Bot...")
            print("=" * 40)

            # single-instance lock: prevent multi-poller conflicts on same host
            # Platform-specific implementation
            import platform
            lock_path = Path(tempfile.gettempdir()) / 'egocore-telegram-poller.lock'

            if platform.system() == 'Windows':
                # Windows: use file locking via msvcrt or portalocker alternative
                try:
                    import msvcrt
                    lock_fd = open(lock_path, 'w')
                    # Try to lock 10 bytes at position 0
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 10)
                    lock_fd.write(f"pid={os.getpid()} host={socket.gethostname()}\n")
                    lock_fd.flush()
                except (IOError, OSError):
                    print(f"\n❌ Telegram poller lock already held: {lock_path}")
                    print("   Refusing to start to avoid getUpdates conflict.")
                    return 2
            else:
                # Unix/Linux/Mac: use fcntl
                import fcntl
                lock_fd = open(lock_path, 'w')
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_fd.write(f"pid={os.getpid()} host={socket.gethostname()}\n")
                    lock_fd.flush()
                except BlockingIOError:
                    print(f"\n❌ Telegram poller lock already held: {lock_path}")
                    print("   Refusing to start to avoid getUpdates conflict.")
                    return 2

            try:
                live_report_path = write_live_process_version_report(process_kind="telegram")
                print(f"  ✓ Live process version report written: {live_report_path}")
            except Exception as e:
                print(f"  ⚠ Failed to write live process version report: {e}")

            # Initialize tools
            from app.tools import setup_tools
            tools_config = config.get('tools', {})
            setup_tools(tools_config)
            print("  ✓ Tools initialized")

            # Import Telegram bot module
            from app.telegram_bot import create_bot_from_config

            try:
                bot = create_bot_from_config(pending_restore_observation=pending_restore_observation)
                print("  ✓ Telegram bot created, starting...")
                bot.run()  # Blocking
            except ConfigError as e:
                print(f"\n❌ Telegram Bot Error: {e}")
                return 1
            except KeyboardInterrupt:
                print("\n\n👋 Bot stopped by user.")
                return 0

        elif not args.status:
            # Default: show next steps
            print("\nNext Steps:")
            print("  1. Copy .env.example to .env")
            print("  2. Configure your API keys in .env")
            print("  3. Configure models and prompts in config/*.yaml")
            print("  4. Run 'python -m app.main --telegram' to start the Telegram bot")
            print("  5. Run 'python -m app.main --status' to check status")
            print("  6. Run 'python -m app.main --dashboard' to inspect read-only observation indexes")

        logger.info("OpenEmotion Agent Runtime initialized")
        return 0

    except ConfigError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease fix the configuration and try again.")
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
