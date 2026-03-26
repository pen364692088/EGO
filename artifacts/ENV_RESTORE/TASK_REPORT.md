# ENV_RESTORE TASK_REPORT

## 任务名称

环境恢复 / 验证基础设施修复

## 任务类型

环境治理 / 验证链恢复 / 工具链修复

## 目标

恢复一个能跑最小回归、能做 editable install、能做 import smoke 的正式验证环境。

## 成功判据

- `python -m pytest` 可用，至少能跑当前主线 smoke / guard tests
- `aiosqlite` 等已知缺失依赖补齐，import smoke 不再被基础依赖阻塞
- Linux 下能完成最小 `venv` / editable install 验证
- 所有当前“环境限制”项都被重新分类为：已解决 / 仍阻塞 / 非必需

## 当前层级

环境恢复层 / 正式验证链重建层

## 当前确定项

- 初始系统 Python 缺 `pip`、`ensurepip`、`pytest`、`aiosqlite`
- `venv` 模块存在，但正式验证链无法直接启动
- 仓库工程配置本身已声明 `pytest`、`aiosqlite` 等依赖，不是“项目没写依赖”

## 关键未知

- 系统缺失项是否能在当前环境内直接修复
- editable install 是否会暴露新的工程配置问题
- `pytest` 跑起来后，失败会属于环境问题还是业务断言问题

## 唯一主执行链

1. 盘点环境阻塞项并分类。
2. 修复系统级工具链：`pip` / `ensurepip` / `venv`。
3. 建独立 Linux venv。
4. 做 `OpenEmotion` 与 `EgoCore` editable install。
5. 跑 import smoke 与最小 smoke / guard tests。
6. 重新分类所有限制项。

## 不做项

- 不修改业务逻辑
- 不把环境问题伪装成测试通过
- 不顺手改 README、E5、Telegram 输出

## 本次实际动作

- 安装系统包：
  - `python3-pip`
  - `python3-venv`
- 确认系统 Python 已恢复：
  - `python3 -m pip`
  - `python3 -m ensurepip`
  - `python3 -m venv`
- 在 Linux 临时目录创建独立验证环境：
  - `/tmp/ego-env-restore-venv`
- 在该 venv 内完成 editable install：
  - `openemotion`
  - `egocore-host[dev,proto-self]`
- 验证 import smoke：
  - `aiosqlite`
  - `emotiond.memory`
  - `openemotion.proto_self.schemas`
  - `app.risk_signal`
  - `app.runtime_v2.proto_self_runtime`
- 运行最小 guard tests：
  - 一组 28 个 smoke/guard tests 全通过
- 运行更大的目标测试集：
  - 环境已可执行
  - 暴露出 1 条真实业务断言失败，不再是环境缺失

## 分类结论

### 已解决

- 系统包缺失：`pip` / `ensurepip` / `venv`
- Python 包缺失：`pytest` / `aiosqlite`
- Linux `venv` 可创建
- editable install 可完成
- import smoke 可执行
- 至少一组主线 guard tests 可执行且通过

### 仍阻塞

- 默认 `pytest` capture 在当前 Codex 执行上下文下触发 `_pytest/capture.py` 的 `FileNotFoundError`
  - 使用 `-s` 可绕过，说明 `pytest` 本体已恢复，但默认 capture 与当前临时目录/执行上下文存在兼容性问题
- `EgoCore/tests/test_runtime_v2_proto_self_runtime.py:29` 仍有 1 条真实断言失败
  - 当前实际值：`critical`
  - 测试预期：`high`
  - 这是业务/测试预期问题，不是环境恢复问题

### 非必需

- 系统 Python 直接安装全量 dev 依赖
  - 本次正式验证链已在独立 venv 中恢复，不要求继续污染系统环境
- 修复 Windows 挂载盘上的历史损坏 venv
  - 当前已有 `/tmp` 下可用正式验证 venv

## 本次结论能证明什么

- 能证明系统级 Python 工具链已恢复到可创建正式验证环境的状态
- 能证明项目依赖已可通过 editable install 安装
- 能证明 `pytest`、`aiosqlite`、import smoke、最小 guard tests 都已恢复到可执行状态
- 能证明当前剩余失败不再是“缺环境”，而是测试基础设施兼容问题和真实业务断言问题

## 本次结论不能证明什么

- 不能证明全仓测试都已通过
- 不能证明默认 `pytest` capture 在所有执行上下文都稳定
- 不能证明 `/mnt/d` 上创建的所有 venv 都不会出现工具链异常

## 后续建议

- 将 `/tmp/ego-env-restore-venv` 作为当前正式验证环境继续使用
- 后续回归统一使用：
  - `/tmp/ego-env-restore-venv/bin/python -m pytest -s ...`
- 单独处理：
  - `EgoCore/tests/test_runtime_v2_proto_self_runtime.py:29` 的预期与 canonical risk 规则不一致问题
  - `pytest` 默认 capture 与当前执行上下文的兼容问题
