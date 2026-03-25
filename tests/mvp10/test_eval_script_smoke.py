"""
MVP-10 T26: Eval Script Smoke Tests

Smoke tests for scripts/eval_mvp10.py:
- Quick mode runs successfully
- Science mode runs successfully
- Replay mode runs successfully
- Output files are created correctly
"""
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestEvalScriptQuick:
    """Smoke tests for quick mode."""
    
    def test_quick_mode_runs(self):
        """Test that quick mode runs without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            # Should succeed
            assert result.returncode == 0, f"Quick mode failed: {result.stderr}"
            
            # Should produce JSON output
            output = json.loads(result.stdout)
            assert output["mode"] == "quick"
            assert output["seed"] == 42
            assert output["total_tests"] > 0
    
    def test_quick_mode_creates_artifacts(self):
        """Test that quick mode creates artifact files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            # Check artifact files exist
            artifacts = Path(tmpdir)
            
            # Should have at least one eval result file
            eval_files = list(artifacts.glob("eval_quick_*.json"))
            assert len(eval_files) > 0, "No eval result file created"
            
            # Should have summary.md
            summary_file = artifacts / "summary.md"
            assert summary_file.exists(), "summary.md not created"
    
    def test_quick_mode_json_output(self):
        """Test JSON output format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "123",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            output = json.loads(result.stdout)
            
            # Check required fields
            assert "mode" in output
            assert "run_id" in output
            assert "seed" in output
            assert "success" in output
            assert "total_tests" in output
            assert "passed_tests" in output
            assert "failed_tests" in output
            assert "duration_ms" in output


class TestEvalScriptScience:
    """Smoke tests for science mode."""
    
    def test_science_mode_runs(self):
        """Test that science mode runs without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "science",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            # Should succeed
            assert result.returncode == 0, f"Science mode failed: {result.stderr}"
            
            output = json.loads(result.stdout)
            assert output["mode"] == "science"
    
    def test_science_mode_creates_evidence(self):
        """Test that science mode creates evidence.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "science",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            evidence_file = Path(tmpdir) / "evidence.json"
            assert evidence_file.exists(), "evidence.json not created"
            
            with open(evidence_file) as f:
                evidence = json.load(f)
            
            assert "categories" in evidence
            assert "overall_evidence_score" in evidence
    
    def test_science_mode_creates_posterior(self):
        """Test that science mode creates posterior.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "science",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            posterior_file = Path(tmpdir) / "posterior.json"
            assert posterior_file.exists(), "posterior.json not created"
            
            with open(posterior_file) as f:
                posterior = json.load(f)
            
            assert "bayes_result" in posterior
            assert "uncertainty_report" in posterior


class TestEvalScriptReplay:
    """Smoke tests for replay mode."""
    
    def test_replay_mode_runs(self):
        """Test that replay mode runs without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First create a run
            create_result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            # Then replay
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "replay",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0, f"Replay mode failed: {result.stderr}"
            
            output = json.loads(result.stdout)
            assert output["mode"] == "replay"
            assert "replay_result" in output
            assert output["replay_result"] is not None
    
    def test_replay_mode_determinism(self):
        """Test that replay mode verifies determinism."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a run
            subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                cwd=str(project_root),
            )
            
            # Replay
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "replay",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            output = json.loads(result.stdout)
            replay_result = output.get("replay_result", {})
            
            assert "deterministic" in replay_result
            # Determinism should be True for same seed


class TestEvalScriptZombieCompare:
    """Smoke tests for --compare zombie option."""
    
    def test_zombie_compare_quick(self):
        """Test zombie comparison in quick mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--compare", "zombie",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            output = json.loads(result.stdout)
            assert output["zombie_comparison"] is not None
            assert "zombie_output" in output["zombie_comparison"]
    
    def test_zombie_compare_science(self):
        """Test zombie comparison in science mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "science",
                    "--compare", "zombie",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                    "--output", "json",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            output = json.loads(result.stdout)
            assert output["zombie_comparison"] is not None
    
    def test_zombie_compare_creates_comparison_file(self):
        """Test that zombie comparison creates comparison.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--compare", "zombie",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            comparison_file = Path(tmpdir) / "comparison.json"
            assert comparison_file.exists(), "comparison.json not created"
            
            with open(comparison_file) as f:
                comparison = json.load(f)
            
            assert "zombie_output" in comparison
            assert "comparison" in comparison


class TestEvalScriptOutputFormat:
    """Test output format and content."""
    
    def test_summary_markdown_format(self):
        """Test that summary.md has correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            summary_file = Path(tmpdir) / "summary.md"
            content = summary_file.read_text()
            
            # Check headers
            assert "# MVP-10 Evaluation Summary" in content
            assert "**Mode**:" in content
            assert "**Run ID**:" in content
            assert "## Results" in content
    
    def test_science_summary_has_evidence_section(self):
        """Test that science mode summary has evidence section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "science",
                    "--seed", "42",
                    "--artifacts-dir", tmpdir,
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            
            summary_file = Path(tmpdir) / "summary.md"
            content = summary_file.read_text()
            
            assert "## Evidence" in content
            assert "## Bayesian Posterior" in content


class TestEvalScriptDeterminism:
    """Test that evaluation is deterministic."""
    
    def test_quick_mode_deterministic(self):
        """Test that quick mode produces same results with same seed."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                result1 = subprocess.run(
                    [
                        sys.executable,
                        str(project_root / "scripts" / "eval_mvp10.py"),
                        "--mode", "quick",
                        "--seed", "42",
                        "--artifacts-dir", tmpdir1,
                        "--output", "json",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                )
                
                result2 = subprocess.run(
                    [
                        sys.executable,
                        str(project_root / "scripts" / "eval_mvp10.py"),
                        "--mode", "quick",
                        "--seed", "42",
                        "--artifacts-dir", tmpdir2,
                        "--output", "json",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                )
                
                output1 = json.loads(result1.stdout)
                output2 = json.loads(result2.stdout)
                
                # Results should be identical
                assert output1["passed_tests"] == output2["passed_tests"]
                assert output1["total_tests"] == output2["total_tests"]
                assert output1["success"] == output2["success"]
    
    def test_different_seeds_different_results(self):
        """Test that different seeds can produce different results."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                result1 = subprocess.run(
                    [
                        sys.executable,
                        str(project_root / "scripts" / "eval_mvp10.py"),
                        "--mode", "quick",
                        "--seed", "42",
                        "--artifacts-dir", tmpdir1,
                        "--output", "json",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                )
                
                result2 = subprocess.run(
                    [
                        sys.executable,
                        str(project_root / "scripts" / "eval_mvp10.py"),
                        "--mode", "quick",
                        "--seed", "123",
                        "--artifacts-dir", tmpdir2,
                        "--output", "json",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                )
                
                output1 = json.loads(result1.stdout)
                output2 = json.loads(result2.stdout)
                
                # Run IDs should be different
                assert output1["run_id"] != output2["run_id"]


class TestEvalScriptImport:
    """Test that the module can be imported and used programmatically."""
    
    def test_import_evaluator(self):
        """Test that MVP10Evaluator can be imported."""
        from scripts.eval_mvp10 import MVP10Evaluator, EvalMode, EvalResult
        
        assert MVP10Evaluator is not None
        assert EvalMode is not None
        assert EvalResult is not None
    
    def test_evaluator_quick_mode(self):
        """Test evaluator quick mode programmatically."""
        from scripts.eval_mvp10 import MVP10Evaluator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = MVP10Evaluator(seed=42, artifacts_dir=tmpdir)
            result = evaluator.run_quick()
            
            assert result.mode == "quick"
            assert result.seed == 42
            assert result.total_tests > 0
    
    def test_evaluator_science_mode(self):
        """Test evaluator science mode programmatically."""
        from scripts.eval_mvp10 import MVP10Evaluator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = MVP10Evaluator(seed=42, artifacts_dir=tmpdir)
            result = evaluator.run_science()
            
            assert result.mode == "science"
            assert result.evidence is not None
            assert result.posterior is not None
    
    def test_evaluator_replay_mode(self):
        """Test evaluator replay mode programmatically."""
        from scripts.eval_mvp10 import MVP10Evaluator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # First create a run
            evaluator1 = MVP10Evaluator(seed=42, artifacts_dir=tmpdir)
            quick_result = evaluator1.run_quick()
            evaluator1.save_results(quick_result)
            
            # Then replay
            evaluator2 = MVP10Evaluator(seed=42, artifacts_dir=tmpdir)
            result = evaluator2.run_replay()
            
            assert result.mode == "replay"
            assert result.replay_result is not None


class TestEvalScriptErrorHandling:
    """Test error handling in evaluation script."""
    
    def test_invalid_mode_error(self):
        """Test that invalid mode returns error."""
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "eval_mvp10.py"),
                "--mode", "invalid_mode",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        
        # Should exit with error
        assert result.returncode != 0
    
    def test_missing_artifacts_dir_created(self):
        """Test that missing artifacts directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir) / "nested" / "artifacts"
            
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "eval_mvp10.py"),
                    "--mode", "quick",
                    "--seed", "42",
                    "--artifacts-dir", str(artifacts_dir),
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
            
            assert result.returncode == 0
            assert artifacts_dir.exists()
