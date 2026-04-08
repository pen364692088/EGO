#!/usr/bin/env python3
"""
Detect and run repo validation commands for the Codex long-run harness.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Check:
    category: str
    name: str
    command: Sequence[str]
    cwd: Path
    source: str
    run_in_fast: bool
    run_in_full: bool
    env_overrides: dict[str, str] | None = None
    report_only: bool = False
    precondition_reason: str | None = None
    requires_health_endpoint: bool = False


@dataclass
class Result:
    category: str
    name: str
    command: str
    source: str
    status: str
    note: str
    returncode: int | None = None


@dataclass
class OpenEmotionRuntime:
    command: list[str]
    label: str
    bootstrap_note: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repo validation checks for Codex long-run tasks")
    parser.add_argument("--mode", choices=["fast", "full"], required=True, help="Validation depth")
    parser.add_argument("--dry-run", action="store_true", help="Print detected commands without executing them")
    return parser.parse_args()


def has_make_target(path: Path, target: str) -> bool:
    if not path.exists():
        return False
    needle = f"{target}:"
    return needle in path.read_text(encoding="utf-8", errors="ignore")


def health_endpoint_available() -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def python_command(path: str | Path) -> list[str]:
    return [str(path)]


def candidate_openemotion_python() -> list[tuple[list[str], str]]:
    candidates: list[tuple[list[str], str]] = []
    env_python = os.environ.get("OPENEMOTION_PYTHON")
    if env_python:
        candidates.append((python_command(env_python), f"OPENEMOTION_PYTHON={env_python}"))

    path_candidates = [
        (ROOT / "OpenEmotion" / ".venv" / "bin" / "python", "OpenEmotion/.venv/bin/python"),
        (ROOT / "OpenEmotion" / "venv" / "bin" / "python", "OpenEmotion/venv/bin/python"),
        (ROOT / "OpenEmotion" / ".venv" / "Scripts" / "python.exe", "OpenEmotion/.venv/Scripts/python.exe"),
        (ROOT / "OpenEmotion" / "venv" / "Scripts" / "python.exe", "OpenEmotion/venv/Scripts/python.exe"),
    ]
    for path, label in path_candidates:
        if path.exists():
            candidates.append((python_command(path), label))

    candidates.append((python_command(sys.executable), f"current interpreter ({sys.executable})"))

    deduped: list[tuple[list[str], str]] = []
    seen: set[str] = set()
    for command, label in candidates:
        key = command[0]
        if key not in seen:
            seen.add(key)
            deduped.append((command, label))
    return deduped


def python_missing_modules(command: Sequence[str], modules: Sequence[str]) -> list[str]:
    probe = [*command, "-c", "import " + ", ".join(modules)]
    proc = subprocess.run(probe, cwd=ROOT / "OpenEmotion", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode == 0:
        return []
    missing: list[str] = []
    for module in modules:
        single = [*command, "-c", f"import {module}"]
        proc = subprocess.run(single, cwd=ROOT / "OpenEmotion", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            missing.append(module)
    return missing


def venv_python_command() -> list[str]:
    venv_dir = ROOT / "OpenEmotion" / "venv"
    if os.name == "nt":
        return [str(venv_dir / "Scripts" / "python.exe")]
    return [str(venv_dir / "bin" / "python")]


def windows_bootstrap_python_command() -> list[str]:
    return [str(ROOT / "OpenEmotion" / ".venv" / "Scripts" / "python.exe")]


def can_use_windows_bootstrap() -> bool:
    return os.name != "nt" and str(ROOT).startswith("/mnt/") and shutil.which("cmd.exe") is not None


def to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and parts[1] == "mnt":
        drive = parts[2].upper()
        tail = "\\".join(parts[3:])
        return f"{drive}:\\{tail}" if tail else f"{drive}:\\"
    return str(resolved)


def should_use_windows_interop(command: Sequence[str], cwd: Path) -> bool:
    if os.name == "nt" or not command:
        return False
    executable = str(command[0]).lower()
    return executable.endswith(".exe") and str(cwd).startswith("/mnt/") and shutil.which("cmd.exe") is not None


def convert_command_for_windows(command: Sequence[str]) -> list[str]:
    converted: list[str] = []
    for index, arg in enumerate(command):
        if index == 0 and str(arg).lower().endswith(".exe"):
            converted.append(to_windows_path(Path(arg)))
            continue
        if isinstance(arg, str) and arg.startswith("/mnt/"):
            candidate = Path(arg)
            if candidate.exists():
                converted.append(to_windows_path(candidate))
                continue
        converted.append(str(arg))
    return converted


def escape_cmd_set_value(value: str) -> str:
    return value.replace("%", "%%").replace('"', '^"')


def build_windows_env_prefix(env_overrides: dict[str, str] | None) -> str:
    if not env_overrides:
        return ""
    assignments = [
        f'set "{key}={escape_cmd_set_value(value)}"'
        for key, value in env_overrides.items()
    ]
    return " && ".join(assignments) + " && "


def run_bootstrap_command(command: Sequence[str], cwd: Path) -> None:
    env = os.environ.copy()
    if os.name != "nt":
        env.setdefault("TMPDIR", "/tmp")
        env.setdefault("TMP", "/tmp")
        env.setdefault("TEMP", "/tmp")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    proc = subprocess.run(list(command), cwd=cwd, env=env, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"bootstrap command failed: {' '.join(command)} (exit={proc.returncode})")


def bootstrap_openemotion_venv() -> OpenEmotionRuntime:
    openemotion_dir = ROOT / "OpenEmotion"
    venv_dir = openemotion_dir / "venv"
    python_cmd = venv_python_command()
    bootstrap_steps: list[Sequence[str]] = []

    if not Path(python_cmd[0]).exists():
        shutil.rmtree(venv_dir, ignore_errors=True)
        bootstrap_steps.append([sys.executable, "-m", "venv", "--copies", str(venv_dir)])
    bootstrap_steps.append([*python_cmd, "-m", "pip", "install", "--upgrade", "setuptools", "wheel"])
    bootstrap_steps.append([*python_cmd, "-m", "pip", "install", "--no-build-isolation", "-e", ".[dev]"])

    for command in bootstrap_steps:
        run_bootstrap_command(command, openemotion_dir)

    return OpenEmotionRuntime(
        command=python_cmd,
        label="OpenEmotion/venv (bootstrapped)",
        bootstrap_note="bootstrapped repo-local OpenEmotion runtime in OpenEmotion/venv",
    )


def run_windows_bootstrap_command(command: str, cwd: Path) -> None:
    windows_cwd = to_windows_path(cwd)
    proc = subprocess.run(["cmd.exe", "/c", f"cd /d {windows_cwd} && {command}"], text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"bootstrap command failed: {command} (exit={proc.returncode})")


def bootstrap_openemotion_windows_venv() -> OpenEmotionRuntime:
    openemotion_dir = ROOT / "OpenEmotion"
    venv_dir = openemotion_dir / ".venv"
    python_cmd = windows_bootstrap_python_command()

    if not Path(python_cmd[0]).exists():
        shutil.rmtree(venv_dir, ignore_errors=True)
        run_windows_bootstrap_command("py -3 -m venv .venv", openemotion_dir)
    run_windows_bootstrap_command(".venv\\Scripts\\python.exe -m pip install --upgrade setuptools wheel", openemotion_dir)
    run_windows_bootstrap_command(".venv\\Scripts\\python.exe -m pip install --no-build-isolation -e .[dev]", openemotion_dir)

    return OpenEmotionRuntime(
        command=python_cmd,
        label="OpenEmotion/.venv/Scripts/python.exe (bootstrapped via cmd.exe)",
        bootstrap_note="bootstrapped repo-local OpenEmotion runtime in OpenEmotion/.venv via Windows Python",
    )


def resolve_openemotion_runtime(*, dry_run: bool) -> OpenEmotionRuntime:
    required_modules = ["fastapi", "pydantic", "pytest", "pytest_asyncio", "requests", "dotenv", "anthropic"]
    for command, label in candidate_openemotion_python():
        if not python_missing_modules(command, required_modules):
            return OpenEmotionRuntime(command=list(command), label=label)
    if dry_run:
        command, label = candidate_openemotion_python()[0]
        return OpenEmotionRuntime(
            command=list(command),
            label=label,
            bootstrap_note="dry-run: no runtime bootstrap attempted",
        )
    if can_use_windows_bootstrap():
        return bootstrap_openemotion_windows_venv()
    return bootstrap_openemotion_venv()


def repo_local_pythonpath(
    entries: Sequence[Path], *, windows: bool = False, include_existing: bool = True
) -> str:
    if windows:
        parts = [to_windows_path(path) for path in entries]
        separator = ";"
    else:
        parts = [str(path) for path in entries]
        separator = os.pathsep
    if include_existing:
        existing = os.environ.get("PYTHONPATH")
        if existing:
            parts.append(existing)
    return separator.join(parts)


def detect_checks(open_runtime: OpenEmotionRuntime) -> List[Check]:
    checks: List[Check] = []

    ego_pyproject = ROOT / "EgoCore" / "pyproject.toml"
    ego_tests = ROOT / "EgoCore" / "tests"
    ego_regression = ROOT / "EgoCore" / "tools" / "run_telegram_mainline_regression.sh"
    open_pyproject = ROOT / "OpenEmotion" / "pyproject.toml"
    open_makefile = ROOT / "OpenEmotion" / "Makefile"
    open_smoke = ROOT / "OpenEmotion" / "test_smoke.py"
    open_typecheck_simple = ROOT / "OpenEmotion" / "verify_typecheck_simple.py"
    open_typecheck = ROOT / "OpenEmotion" / "verify_typecheck.py"
    open_testbot = ROOT / "OpenEmotion" / "scripts" / "run_testbot_scenarios.py"
    repo_lint = ROOT / "scripts" / "codex" / "lint_repo.py"
    open_python_cmd, open_python_label = open_runtime.command, open_runtime.label
    open_runtime_missing = python_missing_modules(
        open_python_cmd,
        ["fastapi", "pydantic", "pytest", "pytest_asyncio", "requests", "dotenv", "anthropic"],
    )
    open_smoke_missing = python_missing_modules(open_python_cmd, ["fastapi", "requests"])
    open_runtime_uses_windows_paths = str(open_python_cmd[0]).lower().endswith(".exe")
    ego_pytest_env = {
        "PYTHONPATH": repo_local_pythonpath(
            [
                ROOT,
                ROOT / "EgoCore",
                ROOT / "EgoCore" / "modules",
                ROOT / "OpenEmotion",
            ]
        )
    }
    openemotion_env = {
        "PYTHONPATH": repo_local_pythonpath(
            [
                ROOT / "OpenEmotion",
                ROOT,
                ROOT / "EgoCore",
                ROOT / "EgoCore" / "modules",
            ],
            windows=open_runtime_uses_windows_paths,
            include_existing=False,
        )
    }

    if ego_pyproject.exists():
        checks.append(
            Check(
                category="build",
                name="EgoCore editable install",
                command=["python3", "-m", "pip", "install", "-e", ".[dev]"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/pyproject.toml",
                run_in_fast=False,
                run_in_full=False,
                report_only=True,
                precondition_reason="setup/bootstrap command, not verification-grade",
            )
        )

    if has_make_target(open_makefile, "venv"):
        checks.append(
            Check(
                category="build",
                name="OpenEmotion venv bootstrap",
                command=["make", "venv"],
                cwd=ROOT / "OpenEmotion",
                source="OpenEmotion/Makefile",
                run_in_fast=False,
                run_in_full=False,
                report_only=True,
                precondition_reason="setup/bootstrap command, not verification-grade",
            )
        )

    if ego_pyproject.exists() and ego_tests.exists():
        checks.append(
            Check(
                category="test",
                name="EgoCore pytest suite",
                command=["python3", "-m", "pytest", "tests/", "-v", "-s"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/pyproject.toml + EgoCore/tests/ via repo-local PYTHONPATH",
                run_in_fast=False,
                run_in_full=True,
                env_overrides=ego_pytest_env,
                precondition_reason="full-only heavy test suite",
            )
        )

    if has_make_target(open_makefile, "test"):
        test_command: Sequence[str] = [*open_python_cmd, "-m", "pytest", "tests/", "-q"]
        source = f"OpenEmotion/pyproject.toml + OpenEmotion/tests/ via {open_python_label}"
        open_test_reason = "full-only heavy test suite"
        if open_runtime_missing:
            open_test_reason = (
                f"{open_python_label} missing modules: {', '.join(open_runtime_missing)}"
            )
        checks.append(
            Check(
                category="test",
                name="OpenEmotion test suite",
                command=test_command,
                cwd=ROOT / "OpenEmotion",
                source=source,
                run_in_fast=False,
                run_in_full=not open_runtime_missing,
                env_overrides=openemotion_env,
                precondition_reason=open_test_reason,
            )
        )

    if repo_lint.exists():
        checks.append(
            Check(
                category="lint",
                name="Codex repo lint",
                command=["python3", "scripts/codex/lint_repo.py"],
                cwd=ROOT,
                source="scripts/codex/lint_repo.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    capability_registry_verify = ROOT / "scripts" / "codex" / "verify_capability_registry.py"
    if capability_registry_verify.exists():
        checks.append(
            Check(
                category="governance",
                name="Capability registry drift gate",
                command=["python3", "scripts/codex/verify_capability_registry.py"],
                cwd=ROOT,
                source="scripts/codex/verify_capability_registry.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    path_classification_verify = ROOT / "scripts" / "codex" / "verify_path_classification.py"
    if path_classification_verify.exists():
        checks.append(
            Check(
                category="governance",
                name="Path classification drift gate",
                command=["python3", "scripts/codex/verify_path_classification.py"],
                cwd=ROOT,
                source="scripts/codex/verify_path_classification.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    proto_self_authority_verify = ROOT / "scripts" / "codex" / "verify_proto_self_single_authority.py"
    if proto_self_authority_verify.exists():
        checks.append(
            Check(
                category="governance",
                name="Proto-Self single-authority drift gate",
                command=["python3", "scripts/codex/verify_proto_self_single_authority.py"],
                cwd=ROOT,
                source="scripts/codex/verify_proto_self_single_authority.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    cleanup_admission_verify = ROOT / "scripts" / "codex" / "verify_cleanup_admission.py"
    if cleanup_admission_verify.exists():
        checks.append(
            Check(
                category="governance",
                name="Cleanup admission drift gate",
                command=["python3", "scripts/codex/verify_cleanup_admission.py"],
                cwd=ROOT,
                source="scripts/codex/verify_cleanup_admission.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    if open_typecheck_simple.exists():
        simple_reason = None
        if open_runtime_missing:
            simple_reason = f"{open_python_label} missing modules: {', '.join(open_runtime_missing)}"
        checks.append(
            Check(
                category="typecheck",
                name="OpenEmotion simple typecheck",
                command=[*open_python_cmd, "verify_typecheck_simple.py"],
                cwd=ROOT / "OpenEmotion",
                source=f"OpenEmotion/verify_typecheck_simple.py via {open_python_label}",
                run_in_fast=simple_reason is None,
                run_in_full=False,
                env_overrides=openemotion_env,
                precondition_reason=simple_reason,
            )
        )

    if open_typecheck.exists():
        checks.append(
            Check(
                category="typecheck",
                name="OpenEmotion full typecheck",
                command=[*open_python_cmd, "verify_typecheck.py"],
                cwd=ROOT / "OpenEmotion",
                source=f"OpenEmotion/verify_typecheck.py via {open_python_label}",
                run_in_fast=False,
                run_in_full=True,
                env_overrides=openemotion_env,
            )
        )

    smoke_reason = None
    if not open_smoke.exists():
        smoke_reason = "missing OpenEmotion/test_smoke.py"
    elif open_smoke_missing:
        smoke_reason = f"{open_python_label} missing modules: {', '.join(open_smoke_missing)}"
    checks.append(
        Check(
            category="e2e/smoke",
            name="OpenEmotion smoke",
            command=[*open_python_cmd, "test_smoke.py"],
            cwd=ROOT / "OpenEmotion",
            source=f"OpenEmotion/test_smoke.py via {open_python_label}",
            run_in_fast=smoke_reason is None,
            run_in_full=False,
            env_overrides=openemotion_env,
            precondition_reason=smoke_reason,
        )
    )

    if ego_regression.exists():
        checks.append(
            Check(
                category="e2e/smoke",
                name="EgoCore Telegram mainline regression",
                command=["bash", "./tools/run_telegram_mainline_regression.sh"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/tools/run_telegram_mainline_regression.sh",
                run_in_fast=False,
                run_in_full=True,
            )
        )

    testbot_reason = None
    if not open_testbot.exists():
        testbot_reason = "missing OpenEmotion/scripts/run_testbot_scenarios.py"
    checks.append(
        Check(
            category="e2e/smoke",
            name="OpenEmotion testbot PR subset",
            command=[
                *open_python_cmd,
                "scripts/run_testbot_scenarios.py",
                "--subset",
                "pr",
                "--output",
                "artifacts/testbot/pr_summary.json",
            ],
                cwd=ROOT / "OpenEmotion",
                source=f"OpenEmotion/scripts/run_testbot_scenarios.py via {open_python_label}",
                run_in_fast=False,
                run_in_full=not open_runtime_missing,
                env_overrides=openemotion_env,
                precondition_reason=testbot_reason,
        )
    )

    return checks


def should_run(check: Check, mode: str) -> tuple[bool, str | None]:
    if check.report_only:
        return False, check.precondition_reason
    if check.precondition_reason and not (check.run_in_fast or check.run_in_full):
        return False, check.precondition_reason
    if mode == "fast" and check.run_in_fast:
        return True, None
    if mode == "full" and check.run_in_full:
        return True, None
    if mode == "fast":
        return False, check.precondition_reason or "full-only heavy test suite"
    return False, check.precondition_reason or "not enabled for this mode"


def run_check(check: Check, *, dry_run: bool) -> Result:
    command_str = " ".join(check.command) if check.command else "(none)"
    should_execute, reason = should_run(check, MODE)
    if not should_execute:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="skipped",
            note=reason or "not selected",
        )
    if dry_run:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="skipped",
            note="dry-run",
        )

    env = os.environ.copy()
    if check.env_overrides:
        env.update(check.env_overrides)
    managed_process = None
    health_note = ""
    if check.requires_health_endpoint and not dry_run:
        try:
            managed_process, health_note = ensure_health_endpoint(
                python_command=[check.command[0]],
                cwd=check.cwd,
            )
        except RuntimeError as exc:
            return Result(
                category=check.category,
                name=check.name,
                command=command_str,
                source=check.source,
                status="failed",
                note=str(exc),
                returncode=1,
            )
    try:
        if should_use_windows_interop(check.command, check.cwd):
            windows_cwd = to_windows_path(check.cwd)
            windows_command = subprocess.list2cmdline(convert_command_for_windows(check.command))
            env_prefix = build_windows_env_prefix(check.env_overrides)
            proc = subprocess.run(
                ["cmd.exe", "/c", f"{env_prefix}cd /d {windows_cwd} && {windows_command}"],
                cwd=ROOT,
                env=env,
                text=True,
            )
        else:
            proc = subprocess.run(
                list(check.command),
                cwd=check.cwd,
                env=env,
                text=True,
            )
    finally:
        if managed_process is not None:
            stop_managed_process(managed_process)
    if proc.returncode == 0:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="success",
            note=health_note or "ok",
            returncode=0,
        )
    return Result(
        category=check.category,
        name=check.name,
        command=command_str,
        source=check.source,
        status="failed",
        note=(health_note + "; " if health_note else "") + f"exit={proc.returncode}",
        returncode=proc.returncode,
    )


def print_summary(results: Iterable[Result]) -> None:
    print(f"Codex verify summary (mode={MODE})")
    print("=" * 96)
    print(f"{'category':<12} {'status':<8} {'name':<34} {'source':<28} note")
    print("-" * 96)
    for result in results:
        print(
            f"{result.category:<12} {result.status:<8} {result.name[:34]:<34} "
            f"{result.source[:28]:<28} {result.note}"
        )
        print(f"  command: {result.command}")


MODE = "fast"


def wait_for_health(timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if health_endpoint_available():
            return True
        time.sleep(0.5)
    return False


def ensure_health_endpoint(*, python_command: Sequence[str], cwd: Path) -> tuple[subprocess.Popen[str] | None, str]:
    if health_endpoint_available():
        return None, "reused existing emotiond health endpoint"

    if port_in_use("127.0.0.1", 18080):
        raise RuntimeError("port 18080 is already in use but /health is unavailable")

    process = subprocess.Popen(
        [*python_command, "-m", "emotiond.main"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if wait_for_health():
        return process, "started temporary emotiond daemon for health-dependent check"

    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=2)
    raise RuntimeError(
        "failed to start emotiond health endpoint: "
        + (stderr.strip() or stdout.strip() or "daemon did not become healthy")
    )


def stop_managed_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    global MODE
    args = parse_args()
    MODE = args.mode
    open_runtime = resolve_openemotion_runtime(dry_run=args.dry_run)
    if open_runtime.bootstrap_note:
        print(f"[verify_repo] {open_runtime.bootstrap_note}")
    checks = detect_checks(open_runtime)
    results = [run_check(check, dry_run=args.dry_run) for check in checks]
    print_summary(results)
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
