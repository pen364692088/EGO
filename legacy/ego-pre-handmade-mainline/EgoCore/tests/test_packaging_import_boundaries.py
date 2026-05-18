from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_egocore_pyproject_declares_main_packages():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "app*" in include
    assert "egocore*" in include
    assert "system_core*" in include
    assert "runtime_metrics_aggregator*" in include


def test_openemotion_pyproject_includes_openemotion_package():
    pyproject = tomllib.loads((ROOT.parent / "OpenEmotion" / "pyproject.toml").read_text(encoding="utf-8"))
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "openemotion*" in include
    assert "emotiond*" in include


def test_mainline_modules_do_not_mutate_sys_path():
    targets = [
        ROOT / "app" / "main.py",
        ROOT / "app" / "runtime_v2" / "loop.py",
        ROOT / "app" / "telegram_bot.py",
        ROOT / "system_core" / "metrics_hook.py",
    ]

    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert "sys.path.insert" not in text
        assert "sys.path.append" not in text


def test_app_package_init_is_lazy():
    text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")

    assert "def __getattr__(name):" in text
    assert "from app.telegram_bot import TelegramBot" not in text
