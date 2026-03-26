# ENV_RESTORE EVIDENCE_TABLE

| claim | evidence | result |
|---|---|---|
| 初始系统缺 `pip` | `python3 -m pip --version` 返回 `No module named pip` | 成立 |
| 初始系统缺 `ensurepip` | `python3 -m ensurepip --version` 返回 `No module named ensurepip` | 成立 |
| 初始系统缺 `pytest` | `python3 -m pytest --version` 返回 `No module named pytest` | 成立 |
| 初始系统缺 `aiosqlite` | import 检查返回 `ModuleNotFoundError: No module named 'aiosqlite'` | 成立 |
| 仓库已声明依赖，不是工程没写 | `EgoCore/pyproject.toml` 与 `OpenEmotion/pyproject.toml` 均声明相关依赖 | 成立 |
| 系统工具链已恢复 | `apt-get install -y python3-pip python3-venv` 完成；`python3 -m pip/ensurepip/venv` 可用 | 成立 |
| Linux venv 已恢复 | `/tmp/ego-env-restore-venv` 创建成功 | 成立 |
| editable install 可行 | `pip install -e OpenEmotion -e EgoCore[dev,proto-self]` 成功 | 成立 |
| `pytest` 已可用 | `/tmp/ego-env-restore-venv/bin/python -m pytest --version` 输出 `pytest 9.0.2` | 成立 |
| `aiosqlite` import smoke 已恢复 | `/tmp/ego-env-restore-venv/bin/python` import `aiosqlite` 输出 `OK` | 成立 |
| host/proto-self import smoke 已恢复 | import `emotiond.memory`、`openemotion.proto_self.schemas`、`app.risk_signal`、`app.runtime_v2.proto_self_runtime` 全部 `OK` | 成立 |
| 一组主线 guard tests 已可运行且通过 | `pytest -s ...` 输出 `28 passed in 3.24s` | 成立 |
| 默认 pytest capture 仍有执行环境兼容问题 | `pytest -q ...` 触发 `_pytest/capture.py` `FileNotFoundError` | 阻塞 |
| 当前至少有 1 条真实非环境失败 | `test_runtime_v2_proto_self_runtime.py:29` 断言 `high` vs `critical` | 成立 |

## 关键命令摘录

| command | output summary |
|---|---|
| `python3 -m pip --version` | 初始失败；修复后 PASS |
| `python3 -m ensurepip --version` | 初始失败；修复后 PASS |
| `python3 -m pytest --version` | 初始失败；新 venv 中 PASS |
| `apt-get install -y python3-pip python3-venv` | PASS |
| `/tmp/ego-env-restore-venv/bin/python -m pip install -e ...` | PASS |
| `/tmp/ego-env-restore-venv/bin/python - <<'PY' ... import ...` | 全部 `OK` |
| `/tmp/ego-env-restore-venv/bin/python -m pytest -s ... -q` | `28 passed in 3.24s` |
| `/tmp/ego-env-restore-venv/bin/python -m pytest ... -q` | FAIL: `_pytest/capture.py` `FileNotFoundError` |
