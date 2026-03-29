# EGO Repo AGENTS

适用范围：`/mnt/d/Project/AIProject/MyProject/Ego`

## Repo overview / must-read files

开始任何正式任务前，先按顺序读取：

1. `PROJECT_MEMORY.md`
2. `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
3. `docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
4. `README.md`
5. 如果改 `EgoCore/`，再读 `EgoCore/README.md`
6. 如果改 `OpenEmotion/`，再读 `OpenEmotion/README.md`
7. 如果存在当前任务单，优先读 `Tasks/active/` 下的 spec / plan / acceptance / status / review 文档

读取优先级：

- 当前任务 spec / acceptance / status
- `PROJECT_MEMORY.md`
- Playbook / package README
- 历史报告与观察文档

历史 artifacts 只能当证据或对照，不自动成为 authority source。

## Directory routing

- `EgoCore/`: 宿主、Telegram 入口、runtime、工具执行、安全、delivery、audit
- `OpenEmotion/`: 主体内核、proto-self、memory、self-model、developmental projection
- `Tasks/`: 任务单、spec、plan、acceptance、status、handoff；新任务默认使用 `Tasks/templates/`
- `scripts/`: 跨仓脚本与 capture runner
- `artifacts/`: 证据、观测、样本；除非任务文档明确引用，否则不是默认真相源
- `docs/`: repo 级治理与开发说明

## Build / run / test / lint / review commands

### Setup / build

仓库根目录没有统一 build 命令。按子仓执行：

- `cd EgoCore && python3 -m pip install -e .[dev]`
- `cd OpenEmotion && make venv`
- `cd OpenEmotion && python3 -m pip install -e .`

### Run

- `cd EgoCore && python3 -m app.main --telegram`
- `cd OpenEmotion && make run`

### Test

- `cd EgoCore && python3 -m pytest tests/ -v`
- `cd EgoCore && ./tools/run_telegram_mainline_regression.sh`
- `cd OpenEmotion && make test`
- `cd OpenEmotion && python3 -m pytest tests/ -q`
- `cd OpenEmotion && python scripts/run_testbot_scenarios.py --subset pr --output artifacts/testbot/pr_summary.json`

### Lint / typecheck

当前仓库没有确认可用的 repo 级统一 lint / typecheck 命令。

- 不要编造 `ruff` / `black` / `mypy` / repo-root CI gate
- 如任务需要静态预检，优先使用 `python3 -m py_compile path/to/file.py`
- 如某一子模块有专用校验脚本，只有在任务 authority source 明确要求时才调用

### Review / preflight

- `python3 -m py_compile path/to/file.py`
- `git diff --check`
- OpenEmotion CI 参考：`OpenEmotion/.github/workflows/emotiond-test.yml`
- Testbot CI 参考：`OpenEmotion/.github/workflows/testbot-e2e.yml`

### Publish

本仓正式发布口径：

- `cmd.exe /c git commit ...`
- `cmd.exe /c git push origin main`

## Acceptance / done definition

- 正式改动默认走：`Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`
- 未接主链、未被真实入口触发、或证据强度不足时，不得报“已完成 / 已闭环 / 已生效”
- 若只完成实现或局部验证，统一报“条件性完成”，并写清 blocker 与下一步最小闭环动作
- 交付前至少留下与任务匹配的最小验证：语法/导入、定向测试或脚本、`git diff --check`
- 任务状态、验证等级、handoff 字段使用 `.agents/references/task-state-and-handoff.md`
- 问题层级、验证/证据口径、completion claim 规则使用 `.agents/references/engineering-evidence-model.md`

## Change constraints / do-not rules

- 保持双核边界：EgoCore 负责宿主与现实裁决；OpenEmotion 负责主体语义与状态
- 一项能力只能有一个权威源；不要把 shim / mirror / cache / fallback 偷升为正式主线
- 默认做最小必要改动，不顺手扩大 scope
- 不要编造命令、schema、状态、验收口径
- 不要把运行噪声、临时样本、日志、无关脏文件混入正式提交
- 提交前如遇 `.git/index.lock`，先确认没有活跃 git 进程，再处理陈旧锁；不要对活锁反复重试
- 当前环境里部分 E2/E3 runner 已知更适合 Windows Python；若 Linux 依赖不全，降级到静态检查或说明验证限制，不要捏造“已跑通”

## Skill routing

- 复杂、模糊、跨模块任务：优先使用 `ego-plan-from-spec`
- 按 spec / plan / acceptance 实现明确里程碑：优先使用 `ego-implement-milestone`
- bug / 回归 / 报错 / failing tests / 主链不生效：优先使用 `ego-bugfix-root-cause`
- 对照验收单、`type_verify`、release gate、admission review 做 review / verify：优先使用 `ego-review-against-acceptance`
- 恢复上下文、继续、接着做：优先使用 `ego-resume-context`
- 交接 / 子代理派发 / brief：显式调用 `ego-handoff-brief`
- 如果同一请求同时带有 `continue` 和明确的 bug / milestone / review / handoff 目标，优先选择更具体的 task skill；只有“恢复状态”本身是主要工作时才使用 `ego-resume-context`
- 如果同一请求同时带有 `plan` 和 `implement`：
  - 目标或 milestone 尚未锁定时，优先使用 `ego-plan-from-spec`
  - 已有明确 step file / implementation task / acceptance slice，且用户明确要求现在动代码时，优先使用 `ego-implement-milestone`

## References

- `.agents/references/engineering-evidence-model.md`
- `.agents/references/task-state-and-handoff.md`
