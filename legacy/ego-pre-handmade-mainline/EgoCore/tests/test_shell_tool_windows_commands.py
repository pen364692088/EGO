from types import SimpleNamespace

from app.tools.shell_tool import ShellTool


def test_shell_tool_allows_windows_commands_case_insensitively():
    tool = ShellTool(
        {
            "allowed_commands": [
                "dir",
                "remove-item",
                "rmdir",
            ]
        }
    )

    assert tool._check_security("DIR") is None
    assert tool._check_security("Remove-Item demo.txt") is None
    assert tool._check_security("RMDIR tempdir") is None


def test_shell_tool_accepts_runtime_v2_param_aliases(monkeypatch, tmp_path):
    tool = ShellTool({"allowed_commands": ["dir"], "timeout": 60})
    captured = {}

    monkeypatch.setattr(
        "app.runtime.tool_doctor.run_preflight",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, user_safe_message=None),
    )

    def fake_execute_command(command, timeout, working_dir):
        captured["command"] = command
        captured["timeout"] = timeout
        captured["working_dir"] = working_dir
        return SimpleNamespace()

    monkeypatch.setattr(tool, "_execute_command", fake_execute_command)

    tool.execute(
        {
            "command": "dir",
            "timeout_seconds": 12,
            "working_dir": str(tmp_path),
        }
    )

    assert captured == {
        "command": "dir",
        "timeout": 12,
        "working_dir": str(tmp_path.resolve()),
    }
