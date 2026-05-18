"""
OpenEmotion Agent Runtime - Configuration Loader

This module handles loading, validating, and providing access to all configuration.
Follows the principle: config externalized, no hardcoding.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """
    Central configuration loader for OpenEmotion Agent Runtime.
    
    Loads configuration from:
    1. Environment variables (.env file)
    2. YAML configuration files (config/*.yaml)
    
    Provides:
    - Validated config access
    - Default values
    - Clear error messages for missing/invalid config
    """
    
    # Required environment variables (will fail if missing)
    REQUIRED_ENV_VARS: Set[str] = set()  # No required env vars for Phase 1
    
    # Required config files
    REQUIRED_CONFIG_FILES: Set[str] = {
        'app.yaml',
        'telegram.yaml',
        'llm.yaml',
        'prompts.yaml',
        'tools.yaml',
        'memory.yaml',
        'openemotion.yaml',
    }
    
    # Default values for config paths
    DEFAULTS = {
        'config_dir': 'config',
        'data_dir': './data',
        'env_file': '.env',
    }
    
    def __init__(self, config_dir: Optional[str] = None, env_file: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_dir: Directory containing YAML config files
            env_file: Path to .env file
        """
        self.config_dir = Path(config_dir or self.DEFAULTS['config_dir'])
        self.env_file = Path(env_file or self.DEFAULTS['env_file'])
        
        # Loaded configuration storage
        self._config: Dict[str, Any] = {}
        self._env: Dict[str, str] = {}
        
        # Track if loaded
        self._loaded = False
    
    def load(self, validate: bool = True) -> 'ConfigLoader':
        """
        Load all configuration.
        
        Args:
            validate: Whether to validate required config
        
        Returns:
            Self for chaining
        
        Raises:
            ConfigError: If configuration is invalid or missing
        """
        # Load environment variables
        self._load_env()
        
        # Load YAML configuration files
        self._load_yaml_configs()
        
        # Validate if requested
        if validate:
            self._validate()
        
        self._loaded = True
        return self
    
    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        # Try to load .env file
        if self.env_file.exists():
            load_dotenv(self.env_file)
        else:
            # Check if .env.example exists and warn
            example_path = self.env_file.with_suffix('.example')
            if example_path.exists():
                print(f"Warning: {self.env_file} not found. "
                      f"Copy {example_path} to {self.env_file} and configure.")
        
        # Store environment variables
        for key, value in os.environ.items():
            self._env[key] = value
    
    def _load_yaml_configs(self) -> None:
        """Load all YAML configuration files."""
        if not self.config_dir.exists():
            raise ConfigError(f"Configuration directory not found: {self.config_dir}")
        
        for config_file in self.REQUIRED_CONFIG_FILES:
            file_path = self.config_dir / config_file
            if not file_path.exists():
                raise ConfigError(f"Required configuration file not found: {file_path}")
            
            # Load YAML file
            with open(file_path, 'r', encoding='utf-8') as f:
                config_name = config_file.replace('.yaml', '')
                self._config[config_name] = yaml.safe_load(f) or {}
    
    def _validate(self) -> None:
        """Validate required configuration."""
        # Check required environment variables
        missing_env = []
        for var in self.REQUIRED_ENV_VARS:
            if var not in self._env or not self._env[var]:
                missing_env.append(var)
        
        if missing_env:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing_env)}. "
                f"Set them in your {self.env_file} file."
            )
        
        # Validate app config
        app_config = self._config.get('app', {}).get('app', {})
        if not app_config.get('name'):
            raise ConfigError("app.yaml: app.name is required")
        
        # Validate LLM config
        llm_config = self._config.get('llm', {})
        if not llm_config.get('default_provider'):
            raise ConfigError("llm.yaml: default_provider is required")
        if not llm_config.get('default_model'):
            raise ConfigError("llm.yaml: default_model is required")
        
        # Validate telegram config if enabled
        telegram_config = self._config.get('telegram', {}).get('telegram', {})
        if telegram_config.get('enabled', False):
            token = self._env.get('TELEGRAM_BOT_TOKEN')
            if not token:
                print("Warning: TELEGRAM_BOT_TOKEN not set. "
                      "Telegram bot will not work without it.")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'app.paths.data_dir')
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable value.
        
        Args:
            key: Environment variable name
            default: Default value if not set
        
        Returns:
            Environment variable value or default
        """
        return self._env.get(key, default)
    
    def require_env(self, key: str) -> str:
        """
        Get required environment variable.
        
        Args:
            key: Environment variable name
        
        Returns:
            Environment variable value
        
        Raises:
            ConfigError: If variable is not set
        """
        value = self._env.get(key)
        if not value:
            raise ConfigError(f"Required environment variable not set: {key}")
        return value
    
    @property
    def app(self) -> Dict[str, Any]:
        """Get app configuration."""
        return self._config.get('app', {}).get('app', {})
    
    @property
    def telegram(self) -> Dict[str, Any]:
        """Get telegram configuration."""
        return self._config.get('telegram', {}).get('telegram', {})
    
    @property
    def llm(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        return self._config.get('llm', {})
    
    @property
    def prompts(self) -> Dict[str, Any]:
        """Get prompts configuration."""
        return self._config.get('prompts', {})
    
    @property
    def tools(self) -> Dict[str, Any]:
        """Get tools configuration."""
        return self._config.get('tools', {}).get('tools', {})
    
    @property
    def memory(self) -> Dict[str, Any]:
        """Get memory configuration."""
        return self._config.get('memory', {}).get('memory_types', {})
    
    @property
    def openemotion(self) -> Dict[str, Any]:
        """Get OpenEmotion bridge configuration."""
        return self._config.get('openemotion', {}).get('bridge', {})
    
    def get_prompt(self, prompt_name: str) -> str:
        """
        Get prompt template by name.
        
        Args:
            prompt_name: Name of the prompt (e.g., 'system_main')
        
        Returns:
            Prompt template string
        """
        prompt = self._config.get('prompts', {}).get(prompt_name)
        if not prompt:
            raise ConfigError(f"Prompt not found: {prompt_name}")
        return prompt
    
    def get_llm_config_for_use_case(self, use_case: str) -> Dict[str, Any]:
        """
        Get LLM configuration for a specific use case.
        
        Args:
            use_case: Use case name (e.g., 'planning', 'execution')
        
        Returns:
            LLM configuration for the use case
        """
        use_cases = self.llm.get('use_cases', {})
        if use_case not in use_cases:
            # Return default config
            return {
                'provider': self.llm.get('default_provider'),
                'model': self.llm.get('default_model'),
            }
        return use_cases[use_case]
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific tool.
        
        Args:
            tool_name: Tool name (e.g., 'file', 'shell', 'python')
        
        Returns:
            Tool configuration dict
        """
        return self.tools.get(tool_name, {}).get('config', {})
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """
        Check if a tool is enabled.
        
        Args:
            tool_name: Tool name
        
        Returns:
            True if tool is enabled
        """
        return self.tools.get(tool_name, {}).get('enabled', False)
    
    def get_path(self, path_name: str) -> Path:
        """
        Get a configured path, resolving relative to project root.
        
        Args:
            path_name: Path configuration key
        
        Returns:
            Resolved Path object
        """
        paths = self._config.get('app', {}).get('paths', {})
        path_value = paths.get(path_name, self.DEFAULTS.get('data_dir', './data'))
        return Path(path_value).resolve()
    
    def __repr__(self) -> str:
        return f"<ConfigLoader loaded={self._loaded}>"


# Global config instance
_config: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """
    Get the global configuration instance.
    
    Returns:
        ConfigLoader instance
    
    Raises:
        ConfigError: If configuration not loaded
    """
    global _config
    if _config is None:
        raise ConfigError("Configuration not loaded. Call load_config() first.")
    return _config


def load_config(config_dir: Optional[str] = None, 
                env_file: Optional[str] = None,
                validate: bool = True) -> ConfigLoader:
    """
    Load and set the global configuration.
    
    Args:
        config_dir: Directory containing YAML config files
        env_file: Path to .env file
        validate: Whether to validate required config
    
    Returns:
        ConfigLoader instance
    """
    global _config
    _config = ConfigLoader(config_dir=config_dir, env_file=env_file)
    _config.load(validate=validate)
    return _config
