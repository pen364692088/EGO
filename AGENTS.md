# EGO Repo AGENTS

适用范围：`/mnt/d/Project/AIProject/MyProject/Ego`

## Repo overview / must-read files

开始任何正式任务前，先按顺序读取：

1. `docs/PROGRAM_STATE_UNIFIED.yaml`
2. 如果存在当前任务单，优先读 `Tasks/active/` 下的 spec / plan / acceptance / status / review 文档
3. 如果任务已进入 Codex 长任务闭环，再读 `docs/codex/tasks/<slug>/SPEC.md`、`PLAN.md`、`IMPLEMENT.md`、`STATUS.md`
4. `PROJECT_MEMORY.md`
5. `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
6. `docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
7. `README.md`
8. 如果改 `Ego_handmade/`，再读 `Ego_handmade/docs/ALGORITHM_INVENTORY.md`
9. 如果只读旧参考实现，再读 `legacy/ego-pre-handmade-mainline/EgoCore/README.md` 或 `legacy/ego-pre-handmade-mainline/OpenEmotion/README.md`

读取优先级：

- 当前任务 spec / acceptance / status
- `docs/PROGRAM_STATE_UNIFIED.yaml`
- active lane / current codex task docs
- `PROJECT_MEMORY.md`（只作广义背景，不覆盖 current authority）
- Playbook / package README
- 历史报告与观察文档

历史 artifacts 只能当证据或对照，不自动成为 authority source。

## Ego_handmade-first rule

- 默认 human/operator 体验主线是 `Ego_handmade/`。
- 允许在明确任务内删除旧模板、重写主循环、牺牲部分旧接口，并优先体验而不是兼容。
- 验收标准可从“测试通过”升级为“测试通过 + 多个真实对话样本更自然”。
- 普通实现细节由 Codex 直接收敛执行；重大项必须先给 Stage Card 并获得确认。
- 重大项包括：主线切换、目录迁移、权限扩大、记忆晋升、删除大块旧代码、`PROGRAM_STATE_UNIFIED` 或 evidence ledger 变更。
- 不要把旧 `semantic_route` / keyword-first route / template fallback 重新引回默认入口；默认路径应保持 `user text -> LLM understanding -> proposal/plan -> gate -> trace`。

## Directory routing

- `Ego_handmade/`: 当前默认 operator-first runtime candidate、memory、permission gate、transaction approval、trace、human-trial harness
- `legacy/ego-pre-handmade-mainline/EgoCore/`: 旧宿主参考实现；只作 legacy reference / fallback / algorithm source
- `legacy/ego-pre-handmade-mainline/OpenEmotion/`: 旧主体内核参考实现；只作 legacy reference / algorithm source
- `legacy/ego-pre-handmade-mainline/ego_desktop_lab/`: 旧 deterministic lab/reference harness；不得恢复为第二套 active runtime
- `Tasks/`: 任务单、spec、plan、acceptance、status、handoff；新任务默认使用 `Tasks/templates/`
- `docs/codex/`: Codex long-run harness 文档、模板、示例、任务目录
- `scripts/`: 跨仓脚本与 capture runner；`scripts/codex/` 承载 long-run harness 工具
- `artifacts/`: 证据、观测、样本；除非任务文档明确引用，否则不是默认真相源
- `docs/`: repo 级治理与开发说明

## Build / run / test / lint / review commands

### Setup / build

仓库根目录没有统一 build 命令。按子仓执行：

- 默认 operator runtime 不需要安装旧双核依赖即可做本地 NoLLM/pytest 验证。
- 旧双核参考实现如需运行，路径已迁移到 `legacy/ego-pre-handmade-mainline/`，只在 legacy/fallback 任务中使用。

### Run

- `cd Ego_handmade && python3 agent_base.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/EgoCore && python3 -m app.main --telegram`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && make run`

### Test

- `TMPDIR=/tmp python3 -m pytest -q Ego_handmade/tests`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/EgoCore && python3 -m pytest tests/ -v`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 -m pytest tests/ -q`

### Lint / typecheck

当前仓库的稳定 lint 入口与 OpenEmotion 专用 typecheck 如下：

- `python3 scripts/codex/lint_repo.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 verify_typecheck_simple.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 verify_typecheck.py`

规则：

- 不要编造 `ruff` / `black` / `mypy` / repo-root CI gate
- 旧 `verify_repo.py` 仍可作为 legacy/fallback 检查，但默认新主线验收优先跑 `Ego_handmade/tests`
- 在 WSL + mounted drive 环境下，OpenEmotion verifier runtime 允许优先使用 Windows Python 驱动的 `OpenEmotion/.venv`，以避开 Linux-side `venv/pip` 的 I/O 卡顿
- 如任务需要静态预检，仍可直接使用 `python3 -m py_compile path/to/file.py`

### Review / preflight

- `python3 -m py_compile path/to/file.py`
- `git diff --check`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/verify_repo.py --mode full`
- OpenEmotion CI 参考：`OpenEmotion/.github/workflows/emotiond-test.yml`
- Testbot CI 参考：`OpenEmotion/.github/workflows/testbot-e2e.yml`

### Publish

本仓正式发布口径：

- `cmd.exe /c git commit ...`
- `cmd.exe /c git push origin main`
- 若改动触及 `WP12` maintenance docs / scripts / artifacts，且要给出 `WP12` maintenance 结论，发布前必须先跑 `PYTHONPATH=OpenEmotion python3 scripts/codex/run_wp12_maintenance_verification.py` 与 `python3 scripts/codex/verify_wp12_maintenance_gate.py --json`

## Acceptance / done definition

- 正式改动默认走：`Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher`
- 未接主链、未被真实入口触发、或证据强度不足时，不得报“已完成 / 已闭环 / 已生效”
- 若只完成实现或局部验证，统一报“条件性完成”，并写清 blocker 与下一步最小闭环动作
- 交付前至少留下与任务匹配的最小验证：语法/导入、定向测试或脚本、`git diff --check`
- 任务状态、验证等级、handoff 字段使用 `.agents/references/task-state-and-handoff.md`
- 问题层级、验证/证据口径、completion claim 规则使用 `.agents/references/engineering-evidence-model.md`

## Codex working gates

- Prime directive: 不追求变更多，追求在最小架构损伤下形成可验证的真实行为变化。
- Gate A: coding 前必须明确 contract / schema / authority source；不清楚就先收敛任务，不进入实现。
- Gate B: completion claim 前必须运行与任务匹配的验证；repo-level wrapper 优先用 `scripts/run_verify.sh fast|full`，它只委托现有 canonical verifier，不另造验证逻辑。
- Gate C: 收口前 review diff，重点检查 regression、第二套逻辑、证据缺口、过度设计、无关 temp/log/runtime JSONL。
- 如果 required check 无法运行，报告 `unavailable` 和具体原因；不得把 unavailable 降级写成 pass。
- 最终报告必须列出 changed files、commands run、test results、evidence paths、unresolved risks、next smallest safe step。

## Fixed collaboration loop

对持续研发 / 研究回合，默认采用固定协作分工：

- 用户负责：
  - 方向
  - 风险边界
  - 是否升级 gate
- Codex 负责：
  - 问题重构
  - 最小实现
  - 验证
  - 记账
  - 结论口径

默认每轮先压成：

1. `Stage Card`
2. `One Hypothesis`
3. `One Change Surface`
4. `Three-Level Verify`
5. `Reviewer Verdict`
6. `Ledger Update`

默认不要把实现细节抛回给用户；只有命中以下条件才停下来要用户拍板：

- 高影响路线取舍
- 需要提升 claim ceiling / 升级 gate
- 缺账号、审批、真实入口、人工观察等外部依赖
- 当前 framing 被证明不值得继续
- 继续推进会明显扩大 scope 或改变产品方向

具体合同见：

- `docs/FIXED_COLLABORATION_LOOP_V1.md`
- `docs/RESEARCH_CAMPAIGN_CONTRACT.md`

## Codex Memory Brain

- 若当前环境已启用 `memory_brain` MCP，处理中高复杂度任务前，先把当前任务压缩成一个短 probe，再调用 `memory_build_context`
- 压缩规则：
  - 只保留 `真实目标 + 子系统/路径 + 关键约束或失败信号`
  - 优先写成 `1-2` 句短描述，不把整份 spec / 长聊天原文直接喂给记忆检索
  - 同时附 `2-5` 个稳定 tags，如模块名、bug class、decision theme
- `memory_build_context` 默认参数应带当前 `repo + cwd/path`；除非任务明确要求，不要打开 cross-repo 注入
- 若任务是架构修改、重复失败、或需要回看相似决策，再用同一份压缩 probe 补一次 `memory_search`
- 任务收口前，若确实产生可复用决策/修复/工作流，先把结果压缩成适合持久化的 summary，再调用 `memory_store` 或 `memory_record_outcome`
- 收口压缩规则：
  - 写清 `改了什么 + 为什么有效/无效 + 适用范围/路径 + 证据来源`
  - 优先 `2-4` 句因果摘要，不存长日志、长对话、原始 trace
  - 未证实的猜测不入稳定记忆；必要时只存 `candidate`
- canonical 晋升仍走 `memory_promote_candidate`；不要直接手写 `.codex/memory/*.jsonl`
- hooks 只允许做 reminder / context injection 示例，默认不做无脑自动写入；真正写库必须经过模型判断或人工确认

## Codex Long-Run Harness

- 长任务正式工作目录固定为 `docs/codex/tasks/<slug>/`
- 开工前按顺序读取：`SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 若任务属于 research / verify / observation / proof / high-unknown，再补读 `EXPLORE.md`
- `STATUS.md` 的 `Current milestone` 是当前执行源；每次只推进一个 milestone
- milestone 完成后默认运行：`python3 scripts/codex/verify_repo.py --mode fast`
- milestone 收口、高风险改动、或任务 closeout 前运行：`python3 scripts/codex/verify_repo.py --mode full`
- 验证失败时，先在当前 milestone 内修复、降级口径、或记录 blocker；不能直接推进下一 milestone
- 每次收口都要记录：`decisions / risks / next step / rollback notes / commands run / evidence`
- 保持 diff scoped，不顺手扩 scope；已有 `Tasks/active/*.md` 或 step/task 文档时，只作为 authority refs 引入，不复制为第二真相源
- 仓库存在 smoke/e2e 能力时，相关长任务必须纳入 smoke/e2e 类验证
- prompt 含 `LONGRUN` 时，进入持续推进模式：默认不为常规实现细节征求用户；只有命中缺外部凭据/审批、authority source 冲突、或验证证明当前 slice 无法闭环时才停

探索型 long-run 任务默认规则：

- 默认模式：`Question Reformulation -> Hypothesis -> Experiment -> Log -> Decision`
- 每次实验后，必须先更新 `EXPLORE.md`，再开始下一轮
- 记录最少包括：
  - 当前 framing
  - 假设
  - 最小实验
  - 观察结果
  - 证明了什么
  - 不能证明什么
  - 排除了什么路线
  - 下一步为什么这么走
- 连续两轮低增益时，必须显式换 framing，而不是继续原路线 brute force
- `candidate_found` 不等于 `proof_passed`；找到候选方案后必须切到 proof / verify 口径

## Change constraints / do-not rules

Before any implementation:
1. Read `docs/PROGRAM_STATE_UNIFIED.yaml`
2. Summarize `current_phase / current_layer / highest_evidence_level / next_minimal_action`
3. State what the task can change and what it cannot prove
4. If implementation changes project state, update `PROGRAM_STATE_UNIFIED.yaml`
5. If implementation changes evidence, update `artifacts/evidence_ledger`
6. Regenerate derived views
7. Never claim a conclusion stronger than the current evidence level

- 保持双核边界：EgoCore 负责宿主与现实裁决；OpenEmotion 负责主体语义与状态
- 在 `Ego_handmade-first` 迁移后，上述双核边界只约束 legacy reference；新默认 runtime 以 `Ego_handmade` 的 operator contract / gate / trace 为准
- 一项能力只能有一个权威源；不要把 shim / mirror / cache / fallback 偷升为正式主线
- 默认做最小必要改动，不顺手扩大 scope
- 不要编造命令、schema、状态、验收口径
- 不要把运行噪声、临时样本、日志、无关脏文件混入正式提交
- 提交前如遇 `.git/index.lock`，先确认没有活跃 git 进程，再处理陈旧锁；不要对活锁反复重试
- 当前环境里部分 E2/E3 runner 已知更适合 Windows Python；若 Linux 依赖不全，降级到静态检查或说明验证限制，不要捏造“已跑通”

## Skill routing

- 多步骤长任务、已有 `docs/codex/tasks/<slug>/`、或 prompt 含 `LONGRUN`：优先使用 `long-run-execution`
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
- 如果同一请求既是长任务持续推进，又带 `continue` / `implement` / `verify`，只要已经存在 `docs/codex/tasks/<slug>/` 或显式出现 `LONGRUN`，优先使用 `long-run-execution`

## References

- 方法论与完成口径：`.agents/references/engineering-evidence-model.md`
- 状态字段与 handoff：`.agents/references/task-state-and-handoff.md`
