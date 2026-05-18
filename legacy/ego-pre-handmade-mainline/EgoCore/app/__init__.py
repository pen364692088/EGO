"""
OpenEmotion Agent Runtime
"""

__version__ = "0.1.0"
__author__ = "OpenEmotion Team"

__all__ = [
    'load_config',
    'get_config',
    'get_logger', 
    'init_logging',
    'TelegramBot',
    'create_bot_from_config',
    'get_bot',
    'CommandRouter',
    'CommandContext',
    'CommandResult',
    'get_router',
]

_EXPORT_MAP = {
    "load_config": ("app.config", "load_config"),
    "get_config": ("app.config", "get_config"),
    "get_logger": ("app.logger", "get_logger"),
    "init_logging": ("app.logger", "init_logging"),
    "TelegramBot": ("app.telegram_bot", "TelegramBot"),
    "create_bot_from_config": ("app.telegram_bot", "create_bot_from_config"),
    "get_bot": ("app.telegram_bot", "get_bot"),
    "CommandRouter": ("app.command_router", "CommandRouter"),
    "CommandContext": ("app.command_router", "CommandContext"),
    "CommandResult": ("app.command_router", "CommandResult"),
    "get_router": ("app.command_router", "get_router"),
}


def __getattr__(name):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module 'app' has no attribute {name!r}")
    module_name, attr_name = _EXPORT_MAP[name]
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
