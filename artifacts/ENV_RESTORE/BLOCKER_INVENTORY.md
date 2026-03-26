# ENV_RESTORE BLOCKER_INVENTORY

## 初始阻塞项盘点

| id | blocker | type | initial symptom | current status |
|---|---|---|---|---|
| B1 | `python3 -m pip` 缺失 | 系统包缺失 | `No module named pip` | 已解决 |
| B2 | `python3 -m ensurepip` 缺失 | 系统包缺失 | `No module named ensurepip` | 已解决 |
| B3 | `python3 -m pytest` 缺失 | Python 包缺失 | `No module named pytest` | 已解决 |
| B4 | `aiosqlite` 缺失 | Python 包缺失 | import smoke 被 `ModuleNotFoundError` 阻塞 | 已解决 |
| B5 | Linux 最小 venv 未形成正式验证链 | 工程/工具链状态问题 | 虽有 `venv`，但无可复用验证环境 | 已解决 |
| B6 | editable install 未验证 | 工程配置风险 | 无法确认 pyproject/build backend 是否可用 | 已解决 |
| B7 | `pytest` 默认 capture 报 `FileNotFoundError` | 测试基础设施假设问题 | `_pytest/capture.py` 在收尾阶段失败 | 仍阻塞 |
| B8 | `test_runtime_v2_proto_self_runtime.py:29` 断言不符 | 测试假设问题 / 业务预期问题 | 预期 `high`，实际 `critical` | 仍阻塞 |
| B9 | `/mnt/d/.../.venv-env-restore` 曾出现半升级 pip | 环境恢复过程故障 | `ModuleNotFoundError: pip._internal.utils` | 非必需，已绕过 |

## 分类说明

### 系统包缺失

- `pip`
- `ensurepip`
- `python3-venv` 对应的系统能力未安装为正式链

### Python 包缺失

- `pytest`
- `aiosqlite`

### 工程配置问题

- 本次未发现 pyproject/editable install 本身失效
- `OpenEmotion/pyproject.toml` 与 `EgoCore/pyproject.toml` 均可构建 editable wheel

### 测试假设问题

- `pytest` 默认 capture 在当前执行上下文不稳定
- `risk_level` 预期值有 1 条仍停留在旧语义
