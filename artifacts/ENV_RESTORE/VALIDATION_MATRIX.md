# ENV_RESTORE VALIDATION_MATRIX

| validation target | command | expected | actual | status |
|---|---|---|---|---|
| system `pip` available | `python3 -m pip --version` | 可执行 | `pip 24.0` | PASS |
| system `ensurepip` available | `python3 -m ensurepip --version` | 可执行 | `pip 24.0` | PASS |
| system `venv` available | `python3 -m venv /tmp/ego-env-restore-venv` | 可创建 venv | 成功 | PASS |
| venv pip available | `/tmp/ego-env-restore-venv/bin/python -m pip --version` | 可执行 | `pip 24.0` | PASS |
| editable install: OpenEmotion | `pip install -e OpenEmotion` | 成功 | 成功 | PASS |
| editable install: EgoCore | `pip install -e EgoCore[dev,proto-self]` | 成功 | 成功 | PASS |
| `pytest` usable | `/tmp/ego-env-restore-venv/bin/python -m pytest --version` | 可执行 | `pytest 9.0.2` | PASS |
| import smoke: `aiosqlite` | import | 不报缺包 | `OK` | PASS |
| import smoke: `emotiond.memory` | import | 不报缺包 | `OK` | PASS |
| import smoke: `openemotion.proto_self.schemas` | import | 不报缺包 | `OK` | PASS |
| import smoke: `app.risk_signal` | import | 不报缺包 | `OK` | PASS |
| import smoke: `app.runtime_v2.proto_self_runtime` | import | 不报缺包 | `OK` | PASS |
| guard tests runnable | `pytest -s ...` | 可执行 | 28 passed | PASS |
| target smoke set without `-s` | `pytest -q ...` | 可执行 | capture `FileNotFoundError` | WARN |
| larger smoke set correctness | `pytest -s ...` | 全绿或暴露真实失败 | 暴露 1 条真实断言失败 | WARN |

## 已通过的最小 guard tests

- `EgoCore/tests/test_risk_signal_authority.py`
- `OpenEmotion/openemotion/proto_self/tests/test_schema_contract.py`
- `EgoCore/tests/test_execution_context_injection.py`

结果：
- `28 passed in 3.24s`

## 已暴露的非环境失败

- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py::test_build_proto_self_ingress_event_uses_runtime_shape`
  - 预期：`high`
  - 实际：`critical`
