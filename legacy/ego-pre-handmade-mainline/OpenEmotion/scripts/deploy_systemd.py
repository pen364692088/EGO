#!/usr/bin/env python3
"""
Deploy systemd user service for OpenEmotion daemon.

This script installs and enables the emotiond systemd user service.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


class SystemdDeployer:
    """Deploy systemd user service for emotiond."""

    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.service_source = self.repo_root / "deploy" / "systemd" / "user" / "emotiond.service"
        self.service_dest_dir = Path.home() / ".config" / "systemd" / "user"
        self.service_dest = self.service_dest_dir / "emotiond.service"

    def check_prerequisites(self) -> bool:
        """Check if systemd is available and user service directory exists."""
        try:
            # Check if systemctl is available
            subprocess.run(["systemctl", "--version"], capture_output=True, check=True)
            
            # Create user service directory if it doesn't exist
            self.service_dest_dir.mkdir(parents=True, exist_ok=True)
            
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ERROR: systemctl not available. Cannot deploy systemd service.")
            return False

    def install_service(self) -> bool:
        """Install the systemd service file."""
        try:
            # Copy service file
            shutil.copy2(self.service_source, self.service_dest)
            print(f"✓ Service file installed to: {self.service_dest}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to install service file: {e}")
            return False

    def enable_service(self) -> bool:
        """Enable and start the systemd service."""
        try:
            # Reload systemd
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            print("✓ Systemd daemon reloaded")
            
            # Enable service
            subprocess.run(["systemctl", "--user", "enable", "emotiond.service"], check=True)
            print("✓ Service enabled")
            
            # Start service
            subprocess.run(["systemctl", "--user", "start", "emotiond.service"], check=True)
            print("✓ Service started")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to enable/start service: {e}")
            return False

    def check_service_status(self) -> bool:
        """Check if service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "emotiond.service"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip() == "active":
                print("✓ Service is active")
                return True
            else:
                print(f"⚠ Service status: {result.stdout.strip()}")
                return False
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to check service status: {e}")
            return False

    def deploy(self) -> bool:
        """Run full deployment process."""
        print("Deploying OpenEmotion systemd user service...")
        
        if not self.check_prerequisites():
            return False
        
        if not self.install_service():
            return False
        
        if not self.enable_service():
            return False
        
        if not self.check_service_status():
            return False
        
        print("\n✅ Deployment completed successfully!")
        print("\nNext steps:")
        print("  systemctl --user status emotiond.service  # Check service status")
        print("  systemctl --user stop emotiond.service    # Stop service")
        print("  systemctl --user restart emotiond.service # Restart service")
        print("  journalctl --user -u emotiond.service     # View logs")
        
        return True


def main():
    """Main deployment function."""
    deployer = SystemdDeployer()
    
    if not deployer.deploy():
        print("\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()