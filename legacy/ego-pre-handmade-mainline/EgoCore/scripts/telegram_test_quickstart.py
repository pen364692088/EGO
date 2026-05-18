#!/usr/bin/env python3
"""
Telegram E2E Test Quickstart - 快速启动脚本

一键运行 Telegram 测试，自动检测环境并执行相应测试。

Usage:
    python scripts/telegram_test_quickstart.py

Features:
    - 自动检测 EgoCore 是否运行
    - 检查配置文件
    - 创建测试文件
    - 运行基础测试套件
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
TEST_FILES = {
    "/tmp/e2e_test_hello.txt": "Hello E2E Test\nThis is a test file.\n",
    "/tmp/e2e_cycle_test.txt": "Cycle Strengthen Test File\n",
}

REQUIRED_CONFIGS = [
    "config/app.yaml",
    "config/telegram.yaml",
    "config/openemotion.yaml",
]


def check_egocore_running() -> bool:
    """Check if EgoCore is running."""
    import psutil

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            if any('app.main' in str(c) for c in cmdline):
                return True
            if any('telegram_bot' in str(c) for c in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def check_configs() -> List[str]:
    """Check if required config files exist."""
    missing = []
    base_path = Path(__file__).parent.parent

    for config in REQUIRED_CONFIGS:
        if not (base_path / config).exists():
            missing.append(config)

    return missing


def create_test_files() -> None:
    """Create test files."""
    print("[SETUP] Creating test files...")

    for path, content in TEST_FILES.items():
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ {path}")
        except Exception as e:
            print(f"  ✗ {path}: {e}")


def check_proto_self_enabled() -> bool:
    """Check if Proto-Self is enabled in config."""
    try:
        from app.config import load_config
        config = load_config()
        return config.openemotion.get('enabled', False)
    except Exception:
        return False


async def run_sim_test(message: str, verify_cycle: bool = False) -> bool:
    """Run a single simulator test."""
    cmd = [
        sys.executable,
        "scripts/telegram_sim_harness.py",
        "--message", message,
    ]
    if verify_cycle:
        cmd.append("--verify-cycle")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        output = stdout.decode('utf-8', errors='replace')
        success = proc.returncode == 0

        print(output)
        return success
    except asyncio.TimeoutError:
        print("[ERROR] Test timeout")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def print_summary(results: Dict[str, Any]) -> None:
    """Print test summary."""
    print("\n" + "=" * 60)
    print("Telegram E2E Quickstart Summary")
    print("=" * 60)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)


async def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Telegram E2E Test Quickstart")
    print("=" * 60)

    results = {}

    # Step 1: Check configs
    print("\n[CHECK] Checking configuration...")
    missing_configs = check_configs()
    if missing_configs:
        print(f"[WARN] Missing config files: {', '.join(missing_configs)}")
    else:
        print("[CHECK] ✓ All config files present")

    # Step 2: Check Proto-Self enabled
    print("\n[CHECK] Checking Proto-Self status...")
    if check_proto_self_enabled():
        print("[CHECK] ✓ Proto-Self is enabled")
        results["proto_self_enabled"] = True
    else:
        print("[CHECK] ✗ Proto-Self is disabled (check config/app.yaml)")
        results["proto_self_enabled"] = False

    # Step 3: Check if EgoCore is running
    print("\n[CHECK] Checking EgoCore status...")
    if check_egocore_running():
        print("[CHECK] ✓ EgoCore appears to be running")
        results["egocore_running"] = True
    else:
        print("[CHECK] ⚠ EgoCore does not appear to be running")
        print("[CHECK]   You may need to start it manually:")
        print("[CHECK]   python -m app.main --telegram")
        results["egocore_running"] = False

    # Step 4: Create test files
    print("\n[SETUP] Setting up test files...")
    create_test_files()
    results["test_files_created"] = True

    # Step 5: Run basic simulator test
    print("\n[TEST] Running basic simulator test...")
    success = await run_sim_test("[QUICKSTART] 读取文件 /tmp/e2e_test_hello.txt", verify_cycle=True)
    results["basic_sim_test"] = success

    # Step 6: Run external failure test
    print("\n[TEST] Running external failure test...")
    success = await run_sim_test("[QUICKSTART] 读取不存在的文件 /tmp/e2e_not_exist_xyz_quick.txt", verify_cycle=True)
    results["external_failure_test"] = success

    # Print summary
    print_summary(results)

    # Final verdict
    if all(results.values()):
        print("\n✅ All checks passed! You're ready for Telegram E2E testing.")
        print("\nNext steps:")
        print("  1. Run full regression: python scripts/regression_proto_self_telegram_e2e.py")
        print("  2. Run scenarios: python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/cycle_strengthen.json")
        print("  3. Start Bot E2E: python scripts/telegram_bot_api_e2e.py --suite smoke")
        return 0
    else:
        print("\n⚠ Some checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
