import json
import os
import sys
from pathlib import Path

import pytest

from emotiond.core import load_initial_state, process_event
from emotiond.db import init_db
from emotiond.models import Event
from emotiond.reflection import ReflectionEngine
from emotiond.narrative_memory import narrative_memory

# Repo root for dynamic path resolution
REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT_LITERAL = json.dumps(str(REPO_ROOT))


@pytest.mark.asyncio
async def test_process_event_emits_self_report_artifacts(tmp_path: Path, monkeypatch):
    """Test that process_event generates self_report with all required fields."""
    # Isolate both DB and reports to tmp_path
    monkeypatch.setenv("EMOTIOND_DB_PATH", str(tmp_path / "mvp8_test.db"))
    monkeypatch.setenv("EMOTIOND_REPORTS_DIR", str(tmp_path / "reports"))

    await init_db()
    await load_initial_state()

    event = Event(
        type="user_message",
        actor="userA",
        target="agent",
        text="thanks, this is great",
        meta={"target_id": "mvp8-session", "reflection_seed": 42},
    )
    result = await process_event(event)

    assert result["status"] == "processed"
    assert "self_report" in result
    assert result["self_report"]["target_id"] == "mvp8-session"
    assert "emotional_reasoning" in result["self_report"]
    assert "self_consistency" in result["self_report"]
    assert Path(result["self_report_path"]).exists()
    assert Path(result["self_report_index_path"]).exists()


def test_reflection_engine_is_deterministic_for_same_inputs(tmp_path: Path, monkeypatch):
    """Test that same input + seed produces same logical outputs and hash.

    Note: narrative_memory is stateful (tracks event_count), so we reset it
    between calls to test pure determinism of the decision logic.
    """
    monkeypatch.setenv("EMOTIOND_REPORTS_DIR", str(tmp_path / "reports"))

    engine = ReflectionEngine(seed=11, base_dir=str(tmp_path / "reports"))

    class _E:
        type = "user_message"
        actor = "u"
        target = "a"
        text = "hello"
        meta = {"target_id": "det"}

    process_result = {
        "appraisal": {
            "goal_progress": 0.1,
            "social_threat": 0.2,
            "intensity": 0.3,
        },
        "prediction_error": 0.15,
        "social_safety": 0.7,
        "regulation_budget": 0.9,
        "energy": 0.8,
        "uncertainty": 0.2,
        "valence": 0.1,
        "arousal": 0.2,
        "energy_budget": 0.95,
        "self_model_result": {},
    }

    # First call
    narrative_memory.reset()  # Reset narrative state
    r1 = engine.build_self_report(_E(), process_result, "det", "u", seed=11)

    # Reset narrative state for second call
    narrative_memory.reset()
    r2 = engine.build_self_report(_E(), process_result, "det", "u", seed=11)

    # Emotional reasoning must be identical
    assert r1["emotional_reasoning"] == r2["emotional_reasoning"]
    assert r1["self_consistency"] == r2["self_consistency"]

    # Narrative memory must be identical (after reset)
    assert r1["narrative_memory"] == r2["narrative_memory"]

    # Hash must be identical
    assert r1["audit"]["self_hash"] == r2["audit"]["self_hash"]


def test_hash_stability_across_different_timestamps(tmp_path: Path, monkeypatch):
    """Test that self_hash excludes non-deterministic fields.

    Verifies that:
    1. generated_at is excluded from stable payload
    2. self_hash is excluded (circular prevention)
    3. hash is computed correctly
    """
    monkeypatch.setenv("EMOTIOND_REPORTS_DIR", str(tmp_path / "reports"))

    engine = ReflectionEngine(seed=42, base_dir=str(tmp_path / "reports"))

    class _E:
        type = "user_message"
        actor = "user"
        target = "agent"
        text = "test hash stability"
        meta = {"target_id": "hash_test"}

    process_result = {
        "appraisal": {"goal_progress": 0.5, "social_threat": 0.3},
        "prediction_error": 0.1,
        "social_safety": 0.8,
        "energy": 0.7,
        "uncertainty": 0.2,
        "valence": 0.3,
        "arousal": 0.4,
        "energy_budget": 0.9,
        "self_model_result": {},
    }

    narrative_memory.reset()  # Reset for clean state
    r1 = engine.build_self_report(_E(), process_result, "hash_test", "user", seed=42)

    # Verify hash excludes generated_at by checking stable payload extraction
    stable = engine._extract_stable_payload(r1)
    assert "generated_at" not in stable, "generated_at must be excluded from stable payload"
    assert "report_path" not in stable, "report_path must be excluded from stable payload"

    # Verify self_hash is excluded from audit in stable payload
    assert "self_hash" not in stable.get("audit", {}), "self_hash must be excluded from audit in stable payload"

    # Verify stable payload hash matches self_hash
    computed_hash = engine._hash_payload(stable)
    assert computed_hash == r1["audit"]["self_hash"], "hash must be computed from stable payload only"


@pytest.mark.asyncio
async def test_scenario_files_count_and_shape():
    """Test that scenario files exist and have correct structure."""
    root = REPO_ROOT / "tests/scenarios/mvp8"
    files = sorted(root.glob("*.json"))
    assert len(files) >= 10, f"Expected at least 10 scenarios, found {len(files)}"

    for f in files:
        sample = json.loads(f.read_text())
        assert "events" in sample or "event" in sample, f"{f.name}: missing event(s)"
        assert "expect" in sample, f"{f.name}: missing expect assertions"


def test_reports_dir_env_isolation(tmp_path: Path, monkeypatch):
    """Test that EMOTIOND_REPORTS_DIR properly isolates report output."""
    custom_dir = tmp_path / "custom_reports"
    monkeypatch.setenv("EMOTIOND_REPORTS_DIR", str(custom_dir))

    engine = ReflectionEngine(seed=1)
    assert engine.base_dir == str(custom_dir), "Engine should use EMOTIOND_REPORTS_DIR"


def test_cross_process_hash_stability(tmp_path: Path, monkeypatch):
    """Test that self_hash is stable across different Python processes.

    This is the hardest determinism test: same input + same seed must
    produce same hash even with different PYTHONHASHSEED.
    """
    import subprocess

    monkeypatch.setenv("EMOTIOND_REPORTS_DIR", str(tmp_path / "reports"))

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    repo_root_literal = json.dumps(str(REPO_ROOT))
    reports_dir_literal = json.dumps(str(reports_dir))

    # Script to build a report and return self_hash (using dynamic repo root)
    script = f'''
import json
import os
import sys
from pathlib import Path

# Dynamic repo root resolution
REPO_ROOT = Path({repo_root_literal})
sys.path.insert(0, str(REPO_ROOT))

os.environ["EMOTIOND_REPORTS_DIR"] = {reports_dir_literal}

from emotiond.reflection import ReflectionEngine
from emotiond.narrative_memory import narrative_memory

engine = ReflectionEngine(seed=42, base_dir={reports_dir_literal})

class _E:
    type = "user_message"
    actor = "user"
    target = "agent"
    text = "cross process test"
    meta = {{"target_id": "cross_proc_test"}}

process_result = {{
    "appraisal": {{"goal_progress": 0.5, "social_threat": 0.3}},
    "prediction_error": 0.1,
    "social_safety": 0.8,
    "energy": 0.7,
    "uncertainty": 0.2,
    "valence": 0.3,
    "arousal": 0.4,
    "energy_budget": 0.9,
    "self_model_result": {{}},
}}

narrative_memory.reset()
r = engine.build_self_report(_E(), process_result, "cross_proc_test", "user", seed=42)
print(json.dumps({{"self_hash": r["audit"]["self_hash"]}}))
'''

    # Run with different PYTHONHASHSEED values
    hashes = []
    for seed in ["0", "1", "12345", "random"]:
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["EMOTIOND_REPORTS_DIR"] = str(reports_dir)

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),  # Use dynamic path
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        output = json.loads(result.stdout.strip())
        hashes.append(output["self_hash"])

    # All processes must produce identical hash
    assert len(set(hashes)) == 1, f"Hash drift across processes: {hashes}"
    print(f"Cross-process hash verified: {hashes[0][:16]}...")
