from app.telegram_bot import TelegramBot


def test_prompt_list_command_shows_loaded_files():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    result = bot._handle_prompt_command("")
    assert result.success is True
    assert "Prompt Files" in result.message
    assert "AGENT.md" in result.message
    assert "SOUL.md" in result.message
    assert "TOOLS.md" in result.message


def test_prompt_show_command_returns_file_content():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    result = bot._handle_prompt_command("show AGENT.md")
    assert result.success is True
    assert "AGENT.md" in result.message
    assert "Session Continuity + Meta-Cognitive Effect Protocol" in result.message


def test_prompt_show_requires_valid_name():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    result = bot._handle_prompt_command("show UNKNOWN.md")
    assert result.success is False
    assert "未找到 prompt 文件" in result.message


def test_prompt_reload_command_reports_loaded_files():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    result = bot._handle_prompt_command("reload")
    assert result.success is True
    assert "Prompt Files Reloaded" in result.message
    assert "AGENT.md" in result.message
