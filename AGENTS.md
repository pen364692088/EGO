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
8. 如果改 `EgoOperator/`，再读 `EgoOperator/docs/ALGORITHM_INVENTORY.md`
9. 如果只读旧参考实现，再读 `legacy/ego-pre-handmade-mainline/EgoCore/README.md` 或 `legacy/ego-pre-handmade-mainline/OpenEmotion/README.md`

读取优先级：

- 当前任务 spec / acceptance / status
- `docs/PROGRAM_STATE_UNIFIED.yaml`
- active lane / current codex task docs
- `PROJECT_MEMORY.md`（只作广义背景，不覆盖 current authority）
- Playbook / package README
- 历史报告与观察文档

历史 artifacts 只能当证据或对照，不自动成为 authority source。

## EgoOperator-first rule

`EgoOperator` is the renamed current operator-first mainline formerly known as `Ego_handmade`.

- 默认 human/operator 体验主线是 `EgoOperator/`。
- 允许在明确任务内删除旧模板、重写主循环、牺牲部分旧接口，并优先体验而不是兼容。
- 验收标准可从“测试通过”升级为“测试通过 + 多个真实对话样本更自然”。
- 普通实现细节由 Codex 直接收敛执行；重大项必须先给 Stage Card 并获得确认。
- 重大项包括：主线切换、目录迁移、权限扩大、记忆晋升、删除大块旧代码、`PROGRAM_STATE_UNIFIED` 或 evidence ledger 变更。
- 不要把旧 `semantic_route` / keyword-first route / template fallback 重新引回默认入口；默认路径应保持 `user text -> LLM understanding -> proposal/plan -> gate -> trace`。

## Directory routing

- `EgoOperator/`: 当前默认 operator-first runtime candidate、memory、permission gate、transaction approval、trace、human-trial harness
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

- `cd EgoOperator && python3 agent_base.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/EgoCore && python3 -m app.main --telegram`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && make run`

### Test

- `TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/EgoCore && python3 -m pytest tests/ -v`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 -m pytest tests/ -q`

### Lint / typecheck

当前仓库的稳定 lint 入口与 OpenEmotion 专用 typecheck 如下：

- `python3 scripts/codex/lint_repo.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 verify_typecheck_simple.py`
- legacy fallback only: `cd legacy/ego-pre-handmade-mainline/OpenEmotion && python3 verify_typecheck.py`

规则：

- 不要编造 `ruff` / `black` / `mypy` / repo-root CI gate
- 旧 `verify_repo.py` 仍可作为 legacy/fallback 检查，但默认新主线验收优先跑 `EgoOperator/tests`
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

- Prime directive: 不追求变更多，也不追求最小 diff；追求最小可验证主线修正。
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
- 在 `EgoOperator-first` 迁移后，上述双核边界只约束 legacy reference；新默认 runtime 以 `EgoOperator` 的 operator contract / gate / trace 为准
- 一项能力只能有一个权威源；不要把 shim / mirror / cache / fallback 偷升为正式主线
- 默认做最小可验证主线修正，不顺手扩大无关 scope
- 不要编造命令、schema、状态、验收口径
- 不要把运行噪声、临时样本、日志、无关脏文件混入正式提交
- 提交前如遇 `.git/index.lock`，先确认没有活跃 git 进程，再处理陈旧锁；不要对活锁反复重试
- 当前环境里部分 E2/E3 runner 已知更适合 Windows Python；若 Linux 依赖不全，降级到静态检查或说明验证限制，不要捏造“已跑通”

## Skill routing

- 跨项目 GitHub Project / 任务板 / 自动推进 / 无人值守 / 扫 Todo / bounded autopilot 控制面：优先使用 `codex-project-autopilot`；先读取 `.codex/project_contract.yaml`，只做 report / plan-next / dry-run loop，除非项目 contract 和当前任务明确允许更高自治级别；EGO 内具体 EgoOperator human-trial/comment/log 修复仍转入 `ego-operator-devloop`
- EgoOperator human-trial / GitHub issue comment / test log / Project closeout / file-web_fetch-approval-memory gate repair loops：优先使用 `ego-operator-devloop`；若同时是 runtime bug / regression，再叠加 `ego-bugfix-root-cause`；若用户给出锁定实现计划，再叠加 `ego-implement-milestone`
- 高风险 EGO/Codex 规划、架构、agent 设计、实现顺序、记忆/权限/工具/状态决策、重复失败，或用户指出“没找到最优解 / framing 不对”时：叠加使用 `ego-reflective-quality-gate`；它是 overlay gate，不替代更具体的 plan / bugfix / implementation / review skill；普通小修只做轻量自检，不强制多轮 reviewer；高风险或反复失败任务在 closeout 前必须做 critic pass，subagent / reviewer 只在当前环境和用户授权允许时启用
- legacy EgoCore/OpenEmotion/OpenClaw 边界、owner、authority source、receipt/main-chain、enablement、trigger evidence 或跨系统漂移问题：使用 `ai-architecture-boundary`；普通 EgoOperator runtime 修复不默认触发该 skill
- 多步骤长任务、已有 `docs/codex/tasks/<slug>/`、或 prompt 含 `LONGRUN`：优先使用 `long-run-execution`
- 复杂、模糊、跨模块任务：优先使用 `ego-plan-from-spec`
- 按 spec / plan / acceptance 实现明确里程碑：优先使用 `ego-implement-milestone`
- bug / 回归 / 报错 / failing tests / 主链不生效：优先使用 `ego-bugfix-root-cause`
- 对照验收单、`type_verify`、release gate、admission review 做 review / verify：优先使用 `ego-review-against-acceptance`
- 恢复上下文、继续、接着做：优先使用 `ego-resume-context`
- 交接 / 子代理派发 / brief：显式调用 `ego-handoff-brief`
- 用户明确点名 `$three-stage-delivery`，或任务确实需要 Plan -> Implement -> Verify -> Critic Review -> Mutation Proof -> Full Verify 的高强度交付闭环时，才使用 `three-stage-delivery`；它不覆盖上述 EGO-specific skills
- 如果同一请求同时带有 `continue` 和明确的 bug / milestone / review / handoff 目标，优先选择更具体的 task skill；只有“恢复状态”本身是主要工作时才使用 `ego-resume-context`
- 如果同一请求同时带有 `plan` 和 `implement`：
  - 目标或 milestone 尚未锁定时，优先使用 `ego-plan-from-spec`
  - 已有明确 step file / implementation task / acceptance slice，且用户明确要求现在动代码时，优先使用 `ego-implement-milestone`
- 如果同一请求既是长任务持续推进，又带 `continue` / `implement` / `verify`，只要已经存在 `docs/codex/tasks/<slug>/` 或显式出现 `LONGRUN`，优先使用 `long-run-execution`

## References

- 方法论与完成口径：`.agents/references/engineering-evidence-model.md`
- 状态字段与 handoff：`.agents/references/task-state-and-handoff.md`

# EGO Codex Execution Policy — EgoOperator-First Aggressive Refactor Mode

你当前工作对象不是旧 EgoCore/OpenEmotion 双核主线，而是 EGO 当前默认 `EgoOperator-first` operator runtime lane。

本节是当前 `EgoOperator` 主线工作的覆盖规则；若与前文旧保守口径冲突，以本节为准。

开始前必须先读：

1. `docs/PROGRAM_STATE_UNIFIED.yaml`
2. 当前 task spec / acceptance / status
3. `AGENTS.md`
4. 如果改 `EgoOperator/`，再读 `EgoOperator/docs/ALGORITHM_INVENTORY.md`

不要把旧 `EgoCore / OpenEmotion / ego_desktop_lab` 重新升格成默认主线。它们现在只作为 legacy reference / fallback / algorithm source，除非当前任务明确授权 legacy/fallback 工作。

## 0. Current Mainline

当前默认路径必须保持：

user text -> LLM understanding -> proposal/plan -> runtime gate -> trace

禁止重新引入：

- keyword-first semantic routing
- template fallback as default entry
- old semantic_route as default path
- old proactive main-chain behavior as default runtime
- old lab shell as production runtime

最小可验证主线修正 = 能触达当前真实入口、当前 mainline owner、runtime gate / trace，并能被验收观察到的最小变更面。小 diff 只是可选手段；如果主循环、主体逻辑、tool loop、memory/gate/trace contract 是根因，就允许修改这些核心面。

## 1. Goal / Claim / Acceptance Language Contract

任务目标必须正向描述要实现的 mechanism，尤其是 selfhood 相关任务。优先写：

- identity continuity
- self-model update
- appraisal signal
- reflection proposal
- bounded initiative
- relationship continuity
- roleplay immersion guard

不要把“不得宣称实现自我意识 / consciousness / real autonomy / subjective experience”写成任务目标。这些只能写在：

- Claim Ceiling
- Reporting Rules
- Acceptance Language
- Not claimed / What This Does Not Prove

Bad:

- 目标：不要宣称实现自我意识。

Good:

- 目标：实现一个可回放的 identity continuity anchor，让 agent 在普通对话、角色演绎和工具场景中稳定使用被用户批准的自称。
- Claim Ceiling：不声明 consciousness、真实主观体验、live autonomy 或稳定用户收益。

## 2. Permission Scope

你可以在必要时激进修改：

- `EgoOperator/agent_base.py`
- runtime modes
- transaction approval
- local operator memory
- permission gate
- trace / audit log
- human-trial harness
- operator comparison harness
- LLM proposal / planner / tool-calling loop
- skill / subagent / team dispatch surface
- current `EgoOperator` 主循环

允许删除旧模板、重写主循环、牺牲部分 legacy interface，并优先真实 operator 体验，而不是兼容旧结构。

## 3. Aggressive Refactor Triggers

如果出现以下情况，不要继续局部补丁，必须提出主循环级或 runtime contract 级重构：

- 用户自然语言被 keyword/template route 压扁
- paraphrase 意义相同但行为分裂
- LLM 没有先理解用户文本，gate 前就被旧规则截断
- 工具/文件/命令/网络/记忆写入没有经过 runtime gate
- memory / todo / subagent 可以直接改核心状态
- trace 不能解释实际行为
- human/operator 体验被兼容旧接口拖累
- 测试通过但多个真实对话样本仍不自然
- 修补一个 case 会继续制造更多模板分支
- 旧 EgoCore/OpenEmotion 代码被复制成第二套 runtime authority

## 4. Mandatory Stage Card

凡涉及以下任一项，先输出 Stage Card，不要直接改：

- 主线切换
- 目录迁移
- 权限扩大
- 记忆晋升
- 删除大块旧代码
- 修改 `PROGRAM_STATE_UNIFIED.yaml`
- 修改 evidence ledger
- 改变 operator contract / gate / trace 的核心语义
- 引入长期自动行动能力
- 引入真实外部通道或真实副作用

Stage Card 必须包含：

- Problem Reframe
- One Hypothesis
- One Change Surface
- Authority Source
- What can change
- What cannot be proven
- Three-Level Verify
- Rollback Plan
- Claim Ceiling

## 5. Implementation Rules

执行时遵守：

1. LLM first for understanding. 不要用 keyword-first route 替代理解。
2. Gate owns side effects. LLM 只能 propose，runtime gate 才能 admit。
3. Trace everything. 关键 proposal / approval / execution / refusal / memory update 都要可追踪。
4. Memory promotion is gated. 不允许工具、subagent、LLM proposal 直接写核心记忆。
5. No second runtime. 不允许把 legacy EgoCore / OpenEmotion / lab shell 恢复成第二套 active runtime。
6. Experience can be acceptance. 如果目标是 operator 体验，验收必须包含多个 human-observable dialogue samples，不能只有 pytest。
7. No overclaim. 当前最高证据不到稳定真实用户收益，不得宣称 live autonomy / stable benefit / consciousness；这些只能作为 Claim Ceiling / Reporting Rules / Acceptance Language，不能替代正向任务目标。
8. Delete dead templates. 如果新路径成立，要删除或隔离旧 template fallback，避免未来继续误用。
9. Prefer mainline correction over local patch. 不追求最小 diff，追求最小可验证主线修正。
10. If checks are unavailable, write unavailable, not pass.

## 6. Required Verification

最小验证按任务选择：

- `python3 -m py_compile path/to/file.py`
- `git diff --check`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- 高风险或 closeout 前：`python3 scripts/codex/verify_repo.py --mode full`
- 改 `EgoOperator/` 时优先跑：`TMPDIR=/tmp python3 -m pytest -q EgoOperator/tests`

如果是 operator 体验改动，还必须提供：

- 至少 3 个自然语言对话样本
- paraphrase 对照，例如“你觉得黑暗之魂怎么样”和“你认为黑暗之魂如何”不应走出不同本质行为
- 样本证明更自然、更少模板味、更少 askback 逃避
- trace 能解释为什么这样回复或为什么拒绝/等待/请求批准

## 7. Completion Report

完成后必须输出：

### Changed Files
列出改动文件。

### Architecture Change
说明是否改了主循环、gate、memory、trace、approval、human-trial harness。

### What Improved
说明真实 operator 体验如何改善。

### Verification Run
列出实际命令和结果。

### Evidence Level
说明当前最高证据层级。不要超过 `PROGRAM_STATE_UNIFIED.yaml` 允许的 claim ceiling。

### What This Does Not Prove
必须写清楚不能证明什么，例如：

- 不证明 stable real user benefit
- 不证明 live autonomy
- 不证明 durable memory efficacy
- 不证明 consciousness
- 不证明所有真实场景稳定

### Next Smallest Safe Step
给出下一步最小闭环动作。
