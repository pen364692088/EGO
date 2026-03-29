# OpenEmotion Environment and Health Stabilization

## Goal

让 `python3 scripts/codex/verify_repo.py --mode full` 不再因为 OpenEmotion 解释器依赖缺失或预先不存在的 `/health` 端点而把验证面降级成环境性 `skipped`。本任务只清理 verifier 的 OpenEmotion runtime/bootstrap 与 health 托管路径，不改 OpenEmotion 业务语义。

## Non-goals

- 不在本任务内修复 OpenEmotion 业务测试失败
- 不改 emotiond 的业务 API、核心状态机或 testbot 业务逻辑
- 不引入新的外部服务、守护进程框架或并行任务体系

## Constraints

- 边界约束：只处理 harness / verifier / 环境 bootstrap / health 托管，不顺手改业务层
- 仓库/子仓约束：复用现有 `OpenEmotion/pyproject.toml`、`OpenEmotion/Makefile`、`scripts/run_daemon.py`、`scripts/eval_suite.py`、`emotiond.main`
- 环境约束：当前 Linux 解释器缺 `fastapi`，且仓库内不存在 `OpenEmotion/venv` 或 `.venv`
- 发布约束：完成后必须回写 `PLAN.md / STATUS.md`，并用 `cmd.exe /c git push origin main` 发布

## Acceptance criteria

- [ ] `verify_repo.py` 能在没有预先存在 `OpenEmotion/venv` 的情况下解析或引导出可用的 OpenEmotion runtime
- [ ] `verify_repo.py --mode fast` 不再因为 OpenEmotion 运行依赖缺失而把 simple typecheck / smoke 直接 `skipped`
- [ ] `verify_repo.py --mode full` 不再因为 `127.0.0.1:18080/health` 事先不可用而把 testbot PR subset 直接 `skipped`
- [ ] 任务文档记录 decisions / risks / next step / rollback notes / commands run / evidence

## Known risks / dependencies

- 风险：runtime bootstrap 可能暴露出此前被 `skipped` 掩盖的真实 OpenEmotion 测试失败
- 风险：health 托管如果不小心处理端口占用，可能和现有本地 daemon 冲突
- 依赖：本机需要能创建 Python venv，并能安装 `OpenEmotion/pyproject.toml` 中声明的依赖
- 外部 blocker：若 pip/bootstrap 因网络或系统 Python 缺组件失败，本 slice 只能收口为环境 blocker

## Authority refs

- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `scripts/codex/verify_repo.py`
- `OpenEmotion/pyproject.toml`
- `OpenEmotion/Makefile`
- `OpenEmotion/scripts/run_daemon.py`
- `OpenEmotion/scripts/eval_suite.py`
- `OpenEmotion/scripts/run_testbot_scenarios.py`
