# Codex Harness Hardening

## Goal

把现有 Codex long-run harness 从“能创建任务目录与汇总命令”推进到“有稳定 lint 入口、统一 OpenEmotion 验证解释器、并在一个真实复杂任务上完成闭环回放”的状态。

## Non-goals

- 不补齐 OpenEmotion 或 EgoCore 的全部环境依赖
- 不改业务主链语义
- 不重做 `Tasks/templates/` 或现有 repo 任务体系
- 不引入新的第三方 lint/typecheck 框架

## Constraints

- 边界约束：只做 harness 框架与验证入口，不做业务功能变更
- 仓库/子仓约束：保持 EgoCore/ OpenEmotion 双核边界，不新造第二任务体系
- 环境约束：当前 Linux `python3` 环境缺 OpenEmotion runtime 依赖；验证脚本必须能清楚区分 success / skipped / failed
- 发布约束：只提交本任务相关文件，使用 `cmd.exe /c git commit` / `git push`

## Acceptance criteria

- [x] 仓库存在稳定、repo-tracked 的 lint 入口，并已接入 `scripts/codex/verify_repo.py`
- [x] OpenEmotion smoke/typecheck 不再硬编码 `.venv`，而是走统一解释器解析规则
- [x] 至少完成一轮真实 long-run task 闭环：任务目录、milestone 推进、验证、状态更新
- [x] `verify_repo.py --mode fast` 能在当前环境下给出更合理的 success / skipped / failed 结果
- [x] 文档已同步 LONGRUN 用法、lint 入口、解释器解析规则

## Known risks / dependencies

- 风险：repo 仍缺完整、统一的 Python 依赖环境；full 模式可能因现有仓库依赖问题失败
- 依赖：现有 `scripts/codex/verify_repo.py`、`OpenEmotion/test_smoke.py`、根 `AGENTS.md`
- 外部 blocker：若后续需要真实 Telegram / emotiond 运行态验证，仍可能受本机环境与服务依赖影响

## Authority refs

- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `AGENTS.md`
- `docs/codex/README.md`
- `OpenEmotion/Makefile`
- `OpenEmotion/pyproject.toml`
