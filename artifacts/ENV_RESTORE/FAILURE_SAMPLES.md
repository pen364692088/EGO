# ENV_RESTORE FAILURE_SAMPLES

## F1. 初始系统缺 pip

- command:
  - `python3 -m pip --version`
- result:
  - `/usr/bin/python3: No module named pip`
- classification:
  - 系统包缺失
- status:
  - 已解决

## F2. 初始系统缺 ensurepip

- command:
  - `python3 -m ensurepip --version`
- result:
  - `/usr/bin/python3: No module named ensurepip`
- classification:
  - 系统包缺失
- status:
  - 已解决

## F3. 初始系统缺 pytest

- command:
  - `python3 -m pytest --version`
- result:
  - `/usr/bin/python3: No module named pytest`
- classification:
  - Python 包缺失
- status:
  - 已解决

## F4. 初始 import smoke 被 aiosqlite 阻塞

- command:
  - import `aiosqlite`
- result:
  - `ModuleNotFoundError: No module named 'aiosqlite'`
- classification:
  - Python 包缺失
- status:
  - 已解决

## F5. `/mnt/d` 上曾出现损坏 venv

- command:
  - `.venv-env-restore/bin/python -m pip install -e ...`
- result:
  - `ModuleNotFoundError: No module named 'pip._internal.utils'`
- classification:
  - 环境恢复过程故障 / 损坏 venv
- status:
  - 非必需，已放弃该 venv，切换到 `/tmp/ego-env-restore-venv`

## F6. 默认 pytest capture 失败

- command:
  - `/tmp/ego-env-restore-venv/bin/python -m pytest ... -q`
- result:
  - `_pytest/capture.py` -> `FileNotFoundError: [Errno 2] No such file or directory`
- classification:
  - 测试基础设施假设问题
- status:
  - 仍阻塞
- workaround:
  - 使用 `-s`

## F7. 非环境的真实测试失败

- command:
  - `/tmp/ego-env-restore-venv/bin/python -m pytest -s EgoCore/tests/test_runtime_v2_proto_self_runtime.py ...`
- result:
  - `EgoCore/tests/test_runtime_v2_proto_self_runtime.py:29`
  - expected: `high`
  - actual: `critical`
- classification:
  - 测试假设问题 / 业务预期不一致
- status:
  - 仍阻塞
