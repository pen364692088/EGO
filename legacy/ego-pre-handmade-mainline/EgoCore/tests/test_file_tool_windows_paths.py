from app.tools.file_tool import FileTool


def test_file_tool_allows_windows_whitelisted_path():
    tool = FileTool(
        {
            "allowed_paths": [
                r"D:\Project\AIProject\MyProject\Test",
                r"D:\Project\AIProject\MyProject\Ego\EgoCore",
            ],
            "allowed_extensions": [".md", ".html", ".txt"],
            "read_only_mode": False,
        }
    )

    path = tool._resolve_and_validate_path(r"D:\Project\AIProject\MyProject\Test\CLAUDE.md")
    assert str(path)


def test_file_tool_allows_windows_subdir_under_allowed_root():
    tool = FileTool(
        {
            "allowed_paths": [
                r"D:\Project\AIProject\MyProject\Ego\EgoCore",
            ],
            "allowed_extensions": [".md", ".html", ".txt"],
            "read_only_mode": False,
        }
    )

    path = tool._resolve_and_validate_path(r"D:\Project\AIProject\MyProject\Ego\EgoCore\temp\CLAUDE.md")
    assert str(path)
