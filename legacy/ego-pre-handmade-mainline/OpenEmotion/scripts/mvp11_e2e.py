#!/usr/bin/env python3
"""Unified MVP11 E2E entry for local + CI runs."""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _run_cmd(cmd: list[str], cwd: str) -> Dict[str, Any]:
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_sec": round(time.time() - t0, 3),
    }


def _latest(pattern: str) -> str | None:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def _load_json(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _effect_gate(full_soak_report_path: str | None, epsilon: float) -> Dict[str, Any]:
    report = _load_json(full_soak_report_path)
    effects = report.get("effect_sizes", {}) if report else {}

    per_prediction: Dict[str, Dict[str, Any]] = {}
    all_pass = True

    for pid in ["P1", "P2", "P3", "P4"]:
        deltas = effects.get(pid, {})
        abs_max = max([abs(float(v)) for v in deltas.values()] + [0.0])
        passed = abs_max > epsilon
        per_prediction[pid] = {
            "epsilon": epsilon,
            "abs_max_delta": round(abs_max, 6),
            "passed": passed,
        }
        all_pass = all_pass and passed

    return {
        "passed": all_pass,
        "epsilon": epsilon,
        "per_prediction": per_prediction,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["ci", "full"], default="full")
    ap.add_argument("--eval-mode", choices=["quick", "science"], default="science")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-replay", action="store_true")
    ap.add_argument("--effect-epsilon", type=float, default=0.005)
    args = ap.parse_args()

    repo_root = str(Path(__file__).resolve().parent.parent)
    artifacts = Path(args.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    # 1) tests/mvp11
    tests_step = _run_cmd([sys.executable, "-m", "pytest", "-q", "tests/mvp11"], cwd=repo_root)

    # 2) eval science/quick
    eval_step = _run_cmd(
        [
            sys.executable,
            "scripts/eval_mvp11.py",
            "--mode",
            args.eval_mode,
            "--seed",
            str(args.seed),
            "--artifacts-dir",
            args.artifacts_dir,
        ],
        cwd=repo_root,
    )

    eval_report_path = _latest(f"{args.artifacts_dir}/eval_{args.eval_mode}_*.json")
    eval_report = _load_json(eval_report_path)
    science_run_id = eval_report.get("run_id")

    # 3) replay on science run
    replay_step = {"skipped": True}
    replay_report_path = None
    if science_run_id and not args.skip_replay:
        replay_step = _run_cmd(
            [
                sys.executable,
                "scripts/eval_mvp11.py",
                "--mode",
                "replay",
                "--run-id",
                science_run_id,
                "--artifacts-dir",
                args.artifacts_dir,
            ],
            cwd=repo_root,
        )
        replay_report_path = f"{args.artifacts_dir}/eval_replay_{science_run_id}.json"

    # 4) full intervention soak (ci/full profile)
    soak_step = _run_cmd(
        [
            sys.executable,
            "scripts/run_full_intervention_soak.py",
            "--profile",
            args.profile,
            "--seed",
            str(args.seed),
            "--artifacts-dir",
            args.artifacts_dir,
        ],
        cwd=repo_root,
    )

    full_soak_report_path = _latest(f"{args.artifacts_dir}/full_soak_report_*.json")
    full_soak_report = _load_json(full_soak_report_path)

    # 5) effect size threshold gate
    effect_gate = _effect_gate(full_soak_report_path, epsilon=args.effect_epsilon)

    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    git_sha = git_sha.stdout.strip() if git_sha.returncode == 0 else "unknown"

    passed = (
        tests_step.get("rc") == 0
        and eval_step.get("rc") == 0
        and (replay_step.get("rc", 0) == 0 if isinstance(replay_step, dict) and not replay_step.get("skipped") else True)
        and soak_step.get("rc") == 0
        and effect_gate.get("passed", False)
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_summary = {
        "pass": passed,
        "git_sha": git_sha,
        "seed": args.seed,
        "ticks": full_soak_report.get("ticks"),
        "science_run_id": science_run_id,
        "profile": args.profile,
        "eval_mode": args.eval_mode,
        "paths": {
            "science_eval": eval_report_path,
            "replay_eval": replay_report_path,
            "full_soak_report": full_soak_report_path,
            "interventions": f"{args.artifacts_dir}/interventions.json",
            "summary_md": f"{args.artifacts_dir}/summary.md",
        },
        "steps": {
            "tests": tests_step,
            "eval": eval_step,
            "replay": replay_step,
            "soak": soak_step,
        },
        "effect_gate": effect_gate,
        "key_metrics": {
            "events": (eval_report.get("metrics") or {}).get("events"),
            "focus_switch_rate": (eval_report.get("metrics") or {}).get("focus_switch_rate"),
            "replan_rate": (eval_report.get("metrics") or {}).get("replan_rate"),
            "governor_block_rate": (eval_report.get("metrics") or {}).get("governor_block_rate"),
        },
        "ts": time.time(),
    }

    out_path = artifacts / f"mvp11_final_summary_{ts}.json"
    out_path.write_text(json.dumps(final_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "pass": passed,
                "final_summary": str(out_path),
                "science_run_id": science_run_id,
                "full_soak_report": full_soak_report_path,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
