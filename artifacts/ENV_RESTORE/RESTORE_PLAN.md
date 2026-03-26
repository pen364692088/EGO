# ENV_RESTORE RESTORE_PLAN

## 三层恢复计划

### 第一层：工具链本身

目标：
- 恢复 `pip` / `ensurepip` / `venv`

执行：
- `apt-get update`
- `apt-get install -y python3-pip python3-venv`

结果：
- 系统 Python 已可执行 `python3 -m pip`
- 系统 Python 已可执行 `python3 -m ensurepip`
- 系统 Python 已可执行 `python3 -m venv`

### 第二层：项目依赖

目标：
- 恢复 `pytest`、`aiosqlite`、editable install、包发现、import smoke

执行：
- 创建 `/tmp/ego-env-restore-venv`
- `pip install -e OpenEmotion -e EgoCore[dev,proto-self]`

结果：
- `openemotion` editable install 成功
- `egocore-host` editable install 成功
- `pytest` / `aiosqlite` / host / proto-self import smoke 成功

### 第三层：验证链

目标：
- 跑一组最小 smoke / guard tests，证明环境恢复是真的

执行：
- 先运行目标测试集，确认 `pytest` 可启动
- 遇到默认 capture 问题后，改用 `-s` 运行最小 guard tests

结果：
- 一组 28 个 smoke / guard tests 通过
- 更大测试集已能运行并暴露真实业务断言失败

## 回退说明

- 不继续修补 `/mnt/d` 上已损坏的 venv
- 统一回退到 `/tmp/ego-env-restore-venv`
- 若后续仍遇到 capture 问题，默认使用 `-s` 作为当前执行环境下的稳定入口
