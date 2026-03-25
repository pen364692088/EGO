#!/usr/bin/env python3
"""
Convenience runner script for emotiond daemon.

This script starts the emotiond daemon with proper virtual environment
activation and environment variable loading.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path


def load_env_file(env_file_path="emotiond.env"):
    """Load environment variables from a file."""
    if os.path.exists(env_file_path):
        print(f"Loading environment variables from {env_file_path}")
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    print(f"  Set {key}")
    else:
        print(f"No environment file found at {env_file_path}")


def find_venv_python():
    """Find the Python executable in the virtual environment."""
    # Check for venv2 directory first (preferred for testing)
    for venv_name in [".venv", "venv"]:
        venv_dir = Path(venv_name)
        if venv_dir.exists():
            if sys.platform == "win32":
                python_exe = venv_dir / "Scripts" / "python.exe"
            else:
                python_exe = venv_dir / "bin" / "python"
            
            if python_exe.exists():
                return str(python_exe)
    
    # Fallback to system Python
    return sys.executable


def start_daemon():
    """Start the emotiond daemon."""
    # Load environment variables
    load_env_file()
    
    # Find Python executable
    python_exe = find_venv_python()
    print(f"Using Python: {python_exe}")
    
    # Check if emotiond module exists
    emotiond_path = Path("emotiond")
    if not emotiond_path.exists():
        print("Error: emotiond directory not found")
        return None
    
    # Start the daemon
    cmd = [python_exe, "-m", "emotiond.main"]
    print(f"Starting emotiond: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Wait a moment to see if it starts successfully
        time.sleep(2)
        
        if process.poll() is not None:
            # Process exited, check for errors
            stdout, stderr = process.communicate()
            print(f"Daemon failed to start:")
            if stdout:
                print(f"STDOUT: {stdout}")
            if stderr:
                print(f"STDERR: {stderr}")
            return None
        
        print("emotiond daemon started successfully")
        return process
    
    except Exception as e:
        print(f"Error starting daemon: {e}")
        return None


def stop_daemon(process):
    """Stop the daemon gracefully."""
    if process and process.poll() is None:
        print("Stopping emotiond daemon...")
        process.terminate()
        try:
            process.wait(timeout=10)
            print("Daemon stopped successfully")
        except subprocess.TimeoutExpired:
            print("Daemon did not stop gracefully, killing...")
            process.kill()


def signal_handler(signum, frame):
    """Handle termination signals."""
    print("\nReceived termination signal, stopping daemon...")
    if 'daemon_process' in globals():
        stop_daemon(globals()['daemon_process'])
    sys.exit(0)


def main():
    """Main function."""
    print("Starting emotiond daemon runner...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the daemon
    process = start_daemon()
    if not process:
        print("Failed to start daemon")
        sys.exit(1)
    
    # Store process globally for signal handler
    globals()['daemon_process'] = process
    
    print("\nemotiond daemon is running. Press Ctrl+C to stop.")
    print("Daemon logs:")
    
    # Monitor the process
    try:
        while process.poll() is None:
            # Read and print any output
            stdout_line = process.stdout.readline()
            if stdout_line:
                print(stdout_line, end='')
            
            stderr_line = process.stderr.readline()
            if stderr_line:
                print(stderr_line, end='')
            
            time.sleep(0.1)
        
        # Process exited
        stdout, stderr = process.communicate()
        if stdout:
            print(f"Final STDOUT: {stdout}")
        if stderr:
            print(f"Final STDERR: {stderr}")
        
        print(f"\nDaemon exited with code {process.returncode}")
        
    except KeyboardInterrupt:
        print("\nStopping daemon...")
        stop_daemon(process)


if __name__ == "__main__":
    main()