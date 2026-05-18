"""
MVP-13 T01: Self-Model Persistence Layer

Handles cross-session persistence of self-model state.
Target: self_model_load_success >= 99%
"""
import os
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from .schema import SelfModelState

logger = logging.getLogger(__name__)


class SelfModelPersistence:
    """
    Persistence layer for self-model state.
    
    Features:
    - Atomic writes with backup
    - JSON serialization
    - Corruption detection and recovery
    - Version migration support
    """
    
    DEFAULT_ARTIFACTS_DIR = "artifacts/mvp13"
    STATE_FILENAME = "self_model_state.json"
    BACKUP_FILENAME = "self_model_state.json.bak"
    TEMP_FILENAME = "self_model_state.json.tmp"
    
    def __init__(
        self,
        artifacts_dir: Optional[str] = None,
        base_dir: Optional[str] = None,
        auto_backup: bool = True,
        max_backups: int = 5
    ):
        """
        Initialize persistence layer.
        
        Args:
            artifacts_dir: Directory for artifacts (relative to base_dir)
            base_dir: Base directory (defaults to current working directory)
            auto_backup: Whether to create backups before overwrites
            max_backups: Maximum number of backup files to keep
        """
        self.base_dir = Path(base_dir or os.getcwd())
        self.artifacts_dir = Path(artifacts_dir or self.DEFAULT_ARTIFACTS_DIR)
        self.full_path = self.base_dir / self.artifacts_dir
        self.auto_backup = auto_backup
        self.max_backups = max_backups
        
        # Ensure directory exists
        self._ensure_directory()
        
        # Statistics
        self._save_count = 0
        self._load_count = 0
        self._error_count = 0
        self._recovery_count = 0
    
    def _ensure_directory(self) -> None:
        """Ensure the artifacts directory exists."""
        self.full_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def state_file(self) -> Path:
        """Path to the state file."""
        return self.full_path / self.STATE_FILENAME
    
    @property
    def backup_file(self) -> Path:
        """Path to the backup file."""
        return self.full_path / self.BACKUP_FILENAME
    
    @property
    def temp_file(self) -> Path:
        """Path to the temp file."""
        return self.full_path / self.TEMP_FILENAME
    
    def save(self, state: SelfModelState) -> bool:
        """
        Save self-model state to disk.
        
        Uses atomic write pattern:
        1. Write to temp file
        2. Backup existing file (if auto_backup)
        3. Rename temp to final
        
        Args:
            state: SelfModelState to save
            
        Returns:
            True if save succeeded, False otherwise
        """
        try:
            # Update timestamp before save
            state.update_timestamp()
            
            # Serialize to JSON
            state_json = state.model_dump_json(indent=2)
            
            # Write to temp file first
            with open(self.temp_file, 'w', encoding='utf-8') as f:
                f.write(state_json)
            
            # Backup existing file if it exists and auto_backup is enabled
            if self.auto_backup and self.state_file.exists():
                self._create_backup()
            
            # Atomic rename
            shutil.move(str(self.temp_file), str(self.state_file))
            
            self._save_count += 1
            logger.info(f"Self-model state saved to {self.state_file}")
            
            return True
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to save self-model state: {e}")
            
            # Clean up temp file if it exists
            if self.temp_file.exists():
                try:
                    self.temp_file.unlink()
                except:
                    pass
            
            return False
    
    def load(self) -> Optional[SelfModelState]:
        """
        Load self-model state from disk.
        
        Attempts to load from main file, falls back to backup if corrupted.
        
        Returns:
            SelfModelState if loaded successfully, None otherwise
        """
        # Try loading main file
        state = self._try_load_file(self.state_file)
        
        if state is not None:
            self._load_count += 1
            logger.info(f"Self-model state loaded from {self.state_file}")
            return state
        
        # Try backup file
        logger.warning("Main state file corrupted, trying backup...")
        state = self._try_load_file(self.backup_file)
        
        if state is not None:
            self._recovery_count += 1
            self._load_count += 1
            logger.info(f"Self-model state recovered from backup {self.backup_file}")
            
            # Save recovered state
            self.save(state)
            
            return state
        
        # Try older backups
        older_backup = self._find_oldest_valid_backup()
        if older_backup is not None:
            state = self._try_load_file(older_backup)
            if state is not None:
                self._recovery_count += 1
                self._load_count += 1
                logger.info(f"Self-model state recovered from {older_backup}")
                self.save(state)
                return state
        
        self._error_count += 1
        logger.error("Failed to load self-model state from any source")
        return None
    
    def _try_load_file(self, file_path: Path) -> Optional[SelfModelState]:
        """Try to load and validate state from a file."""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SelfModelState.model_validate(data)
            
            # Verify identity integrity
            if not state.verify_identity_integrity():
                logger.warning(f"Identity integrity check failed for {file_path}")
                return None
            
            return state
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to load {file_path}: {e}")
            return None
    
    def _create_backup(self) -> None:
        """Create a backup of the current state file."""
        if not self.state_file.exists():
            return
        
        try:
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.full_path / f"self_model_state_{timestamp}.json"
            
            shutil.copy2(str(self.state_file), str(backup_path))
            logger.debug(f"Created backup: {backup_path}")
            
            # Also update the main backup file
            shutil.copy2(str(self.state_file), str(self.backup_file))
            
            # Clean up old backups
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _find_oldest_valid_backup(self) -> Optional[Path]:
        """Find the oldest valid backup file."""
        try:
            backups = sorted(
                self.full_path.glob("self_model_state_*.json"),
                key=lambda p: p.stat().st_mtime
            )
            
            for backup in backups:
                state = self._try_load_file(backup)
                if state is not None:
                    return backup
            
        except Exception as e:
            logger.warning(f"Error finding backups: {e}")
        
        return None
    
    def _cleanup_old_backups(self) -> None:
        """Remove old backups beyond max_backups."""
        try:
            backups = sorted(
                self.full_path.glob("self_model_state_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Keep only the most recent max_backups
            for old_backup in backups[self.max_backups:]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up backups: {e}")
    
    def exists(self) -> bool:
        """Check if state file exists."""
        return self.state_file.exists()
    
    def delete(self) -> bool:
        """
        Delete the state file and backups.
        
        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            # Delete main file
            if self.state_file.exists():
                self.state_file.unlink()
            
            # Delete backup
            if self.backup_file.exists():
                self.backup_file.unlink()
            
            # Delete timestamped backups
            for backup in self.full_path.glob("self_model_state_*.json"):
                backup.unlink()
            
            logger.info("Self-model state files deleted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete state files: {e}")
            return False
    
    def get_statistics(self) -> dict:
        """Get persistence statistics."""
        return {
            "save_count": self._save_count,
            "load_count": self._load_count,
            "error_count": self._error_count,
            "recovery_count": self._recovery_count,
            "success_rate": (
                self._load_count / (self._load_count + self._error_count)
                if (self._load_count + self._error_count) > 0 else 1.0
            ),
            "state_file_exists": self.state_file.exists(),
            "backup_file_exists": self.backup_file.exists(),
            "backup_count": len(list(self.full_path.glob("self_model_state_*.json"))),
        }
    
    def verify_integrity(self) -> Tuple[bool, str]:
        """
        Verify the integrity of the persisted state.
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not self.state_file.exists():
            return False, "State file does not exist"
        
        state = self._try_load_file(self.state_file)
        if state is None:
            return False, "State file is corrupted"
        
        if not state.verify_identity_integrity():
            return False, "Identity integrity check failed"
        
        violations = state.check_identity_invariants()
        if violations:
            return False, f"Invariant violations: {violations}"
        
        return True, "State is valid"


# Singleton instance
_persistence_instance: Optional[SelfModelPersistence] = None


def get_persistence(
    artifacts_dir: Optional[str] = None,
    base_dir: Optional[str] = None
) -> SelfModelPersistence:
    """
    Get or create the singleton persistence instance.
    
    Args:
        artifacts_dir: Override default artifacts directory
        base_dir: Override default base directory
        
    Returns:
        SelfModelPersistence instance
    """
    global _persistence_instance
    
    if _persistence_instance is None:
        _persistence_instance = SelfModelPersistence(
            artifacts_dir=artifacts_dir,
            base_dir=base_dir
        )
    
    return _persistence_instance


def reset_persistence() -> None:
    """Reset the singleton persistence instance (for testing)."""
    global _persistence_instance
    _persistence_instance = None
