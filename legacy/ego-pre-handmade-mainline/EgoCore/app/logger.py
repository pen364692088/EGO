"""
OpenEmotion Agent Runtime - Logging System

Provides structured logging with file and console output.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from logging.handlers import RotatingFileHandler


class AppLogger:
    """
    Application logger with file and console output.
    
    Features:
    - Rotating file handler
    - Console output
    - Configurable format
    - Module-specific loggers
    """
    
    def __init__(self, 
                 name: str = "openemotion",
                 level: str = "INFO",
                 log_format: Optional[str] = None,
                 file_path: Optional[str] = None,
                 max_file_size_mb: int = 10,
                 backup_count: int = 5,
                 console_enabled: bool = True,
                 file_enabled: bool = True):
        """
        Initialize the logger.
        
        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_format: Custom log format string
            file_path: Path to log file
            max_file_size_mb: Maximum log file size in MB
            backup_count: Number of backup files to keep
            console_enabled: Enable console output
            file_enabled: Enable file output
        """
        self.name = name
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.log_format = log_format or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.file_path = file_path
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self.console_enabled = console_enabled
        self.file_enabled = file_enabled
        
        # Root logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(self.level)
        self._logger.handlers.clear()
        
        # Formatter
        self._formatter = logging.Formatter(self.log_format)
        
        # Setup handlers
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Setup logging handlers."""
        # Console handler
        if self.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_handler.setFormatter(self._formatter)
            self._logger.addHandler(console_handler)
        
        # File handler
        if self.file_enabled and self.file_path:
            # Create directory if needed
            log_dir = Path(self.file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                self.file_path,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(self.level)
            file_handler.setFormatter(self._formatter)
            self._logger.addHandler(file_handler)
    
    def get_logger(self, module_name: Optional[str] = None) -> logging.Logger:
        """
        Get a logger for a specific module.
        
        Args:
            module_name: Module name (e.g., 'telegram', 'runtime')
        
        Returns:
            Logger instance
        """
        if module_name:
            return logging.getLogger(f"{self.name}.{module_name}")
        return self._logger
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self._logger.exception(msg, *args, **kwargs)


def setup_logging(config: dict) -> AppLogger:
    """
    Setup logging from configuration.
    
    Args:
        config: Logging configuration dict
    
    Returns:
        Configured AppLogger instance
    """
    return AppLogger(
        name=config.get('name', 'openemotion'),
        level=config.get('level', 'INFO'),
        log_format=config.get('format'),
        file_path=config.get('file_path') if config.get('file_enabled', True) else None,
        max_file_size_mb=config.get('max_file_size_mb', 10),
        backup_count=config.get('backup_count', 5),
        console_enabled=config.get('console_enabled', True),
        file_enabled=config.get('file_enabled', True),
    )


# Global logger instance
_logger: Optional[AppLogger] = None


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        module_name: Optional module name for sub-logger
    
    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        # Create default logger if not set up
        _logger = AppLogger()
    return _logger.get_logger(module_name)


def init_logging(config: dict) -> AppLogger:
    """
    Initialize global logging from configuration.
    
    Args:
        config: Logging configuration dict
    
    Returns:
        Configured AppLogger instance
    """
    global _logger
    _logger = setup_logging(config)
    return _logger
