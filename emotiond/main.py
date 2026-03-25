#!/usr/bin/env python3
"""
Main entry point for emotiond daemon

US-705: Offline Rollouts are disabled by default.
Use --enable-rollouts to enable for diagnostic/recovery scenarios.
"""
import argparse
import os
import sys

# Import config at module level for test access
from emotiond.config import HOST as DEFAULT_HOST
from emotiond.config import PORT as DEFAULT_PORT

# Expose for tests
HOST = DEFAULT_HOST
PORT = DEFAULT_PORT


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenEmotion Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  emotiond                          # Start daemon (rollouts disabled)
  emotiond --enable-rollouts        # Start with rollouts enabled
  emotiond --port 8080              # Start on custom port
        """
    )
    parser.add_argument(
        "--enable-rollouts",
        action="store_true",
        default=False,
        help="Enable offline rollouts (disabled by default for safety)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("EMOTIOND_HOST", HOST),
        help=f"Host to bind to (default: {HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("EMOTIOND_PORT", str(PORT))),
        help=f"Port to bind to (default: {PORT})"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set environment variables based on CLI args
    if args.enable_rollouts:
        os.environ["EMOTIOND_ENABLE_ROLLOUTS"] = "1"
    
    # Import after setting env vars so config picks them up
    import uvicorn
    
    # Use CLI args
    host = args.host
    port = args.port
    
    uvicorn.run(
        "emotiond.api:app",
        host=host,
        port=port,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
