from pathlib import Path

from app.config import ConfigLoader
from app.live_process_version import build_live_process_version_record
from app.repo_paths import get_egocore_root, get_repo_root


def test_repo_root_helper_uses_env_override(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    monkeypatch.setenv("EGO_REPO_ROOT", str(repo_root))

    assert get_repo_root() == repo_root.resolve()
    assert get_egocore_root() == (repo_root / "EgoCore").resolve()


def test_config_loader_resolves_relative_paths_from_overridden_egocore_root(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    ego_root = repo_root / "EgoCore"
    monkeypatch.setenv("EGO_REPO_ROOT", str(repo_root))

    loader = ConfigLoader()

    assert loader.config_dir == (ego_root / "config").resolve()
    assert loader.env_file == (ego_root / ".env").resolve()
    assert loader.get_path("data_dir") == (ego_root / "data").resolve()


def test_live_process_version_uses_env_override_repo_root(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    monkeypatch.setenv("EGO_REPO_ROOT", str(repo_root))

    record = build_live_process_version_record(
        process_kind="telegram",
        argv=["python", "app/main.py", "--telegram"],
        cwd=str((repo_root / "EgoCore").resolve()),
    )

    assert Path(record["repo_root"]).resolve() == repo_root.resolve()
