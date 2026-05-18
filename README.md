# EGO - AI Agent Monorepo

EGO 是 AI Agent 项目的总仓。当前默认 human/operator 体验主线已经切到 `EgoOperator`（formerly `Ego_handmade`）；旧 `EgoCore`、`OpenEmotion`、`ego_desktop_lab` 已降为 legacy reference / fallback / algorithm source。

## 新代理 / 开发者最快入口

- 先读 [docs/MAINLINE_QUICKSTART.md](docs/MAINLINE_QUICKSTART.md)，用它在 5 分钟内确认当前主线、owner 边界和禁止重开的历史线。
- 权威状态只以 [docs/PROGRAM_STATE_UNIFIED.yaml](docs/PROGRAM_STATE_UNIFIED.yaml) 为准。
- 当前 lane 视图看 [docs/codex/tasks/TASK_LANE_INDEX.md](docs/codex/tasks/TASK_LANE_INDEX.md)。
- worktree / operational exhaust 边界看 [docs/REPO_HYGIENE_POLICY.md](docs/REPO_HYGIENE_POLICY.md)。
- repo surface 分类看 [docs/REPO_SURFACE_MAP.md](docs/REPO_SURFACE_MAP.md)。

## 当前权威状态（2026-05-18）

当前正式口径如下：

- `EgoOperator` 是默认 operator-first implementation lane：自然语言先由 LLM 理解，再进入 runtime gate / approval / memory / trace。
- `EgoCore`、`OpenEmotion`、`ego_desktop_lab` 已移动到 `legacy/ego-pre-handmade-mainline/`，只作为可追溯 reference、fallback 和算法素材，不再是默认新开发入口。
- 旧 `subject-system-v1-governed-proactivity` 的证据链保留为 historical evidence；它不再承担默认体验主线。
- 本阶段只记录 `EgoOperator naming/docs safety transition recorded`，不声明 live autonomy、runtime efficacy、稳定用户收益或 consciousness。
- `EgoOperator` 当前已具备 local candidate 级 operator runtime：memory、permission gate、operator comparison、real-use gate、human operator trial scaffold、runtime contract。
- `MVS-aligned compact` 已因 frozen replay gate failure 降为 closed evidence / supporting line，不再是当前主实现线
- `WP17 / MVP22` 不删除，但当前降为 parked bounded lane，不再是默认最高优先级 implementation track
- 旧 Telegram / proactive / proto-self 证据仍可参考，但新任务默认不继续在旧语义路由、模板 fallback、旧主动性链路上补丁。
- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 repo 处于 `EgoOperator-first naming/docs safety transition recorded`
- 当前 archive/governance closeout 新增 `legacy/ego-pre-handmade-mainline/` 作为旧三项目保留位置
- 其余事项仅保留在 `optional housekeeping / future cleanup backlog`
- 这不是 real-channel 新效果声明，也不是长期记忆或主体性正式有效声明
- thin substrate / compat / reference-only 残留仍存在，但已被归入非阻塞边界

## 当前正式口径

- `identity invariants / self-model / drives / reflection / developmental` 的单一权威收口决策见 [docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- 旧正式/compat/reference/deprecated 路径登记保留在 [legacy/ego-pre-handmade-mainline/EgoCore/docs/05_DEPRECATED_AND_SHIMS.md](legacy/ego-pre-handmade-mainline/EgoCore/docs/05_DEPRECATED_AND_SHIMS.md)
- `H1`、Trial helper、旧 comparator 线当前都只算 research/reference/supporting lines，不与 formal runtime mainline 竞争 authority
- `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得描述成“已经强烈体现自我意识”
- 允许的结论只能是 controlled axis、bounded influence、proposal discipline、host-governed bounded expression

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- `docs/archive/ARCHIVE_INDEX.yaml` 与第一批 admitted medium migration 已冻结为当前 archive/governance closeout
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`；未来只有显式授权或决定性 caller proof 才会重开
- 相关 closeout 证据见 [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)

## 当前权威入口

- [docs/PROGRAM_STATE_UNIFIED.yaml](docs/PROGRAM_STATE_UNIFIED.yaml)
- [docs/STATUS.md](docs/STATUS.md)
- [docs/OVERALL_PROGRESS.md](docs/OVERALL_PROGRESS.md)
- [EgoOperator/agent_base.py](EgoOperator/agent_base.py)
- [docs/codex/tasks/ego-operator-human-operator-trial-v2/STATUS.md](docs/codex/tasks/ego-operator-human-operator-trial-v2/STATUS.md)
- [docs/codex/tasks/ego-operator-rename-docs-safety-v1/STATUS.md](docs/codex/tasks/ego-operator-rename-docs-safety-v1/STATUS.md)
- [docs/codex/tasks/ego-mainline-demotion-v1/STATUS.md](docs/codex/tasks/ego-mainline-demotion-v1/STATUS.md)
- [docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- [legacy/ego-pre-handmade-mainline/EgoCore/docs/05_DEPRECATED_AND_SHIMS.md](legacy/ego-pre-handmade-mainline/EgoCore/docs/05_DEPRECATED_AND_SHIMS.md)
- [docs/CURRENT_PROJECT_LOGIC_FLOW.md](docs/CURRENT_PROJECT_LOGIC_FLOW.md)
- [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [docs/CAPABILITY_REGISTRY.md](docs/CAPABILITY_REGISTRY.md)
- [docs/ACCEPTANCE_CHAINS.md](docs/ACCEPTANCE_CHAINS.md)
- [docs/EXPERIENCE_SCRIPTS.md](docs/EXPERIENCE_SCRIPTS.md)

## 当前派生治理与证据入口

- [docs/codex/tasks/TASK_LANE_INDEX.md](docs/codex/tasks/TASK_LANE_INDEX.md)
- [docs/REPO_HYGIENE_POLICY.md](docs/REPO_HYGIENE_POLICY.md)
- [artifacts/telegram_real_mainline_v1/dashboard_v1/DASHBOARD_STAGE1_LIVE_RUN_CURRENT.md](artifacts/telegram_real_mainline_v1/dashboard_v1/DASHBOARD_STAGE1_LIVE_RUN_CURRENT.md)
- [artifacts/telegram_real_mainline_v1/dashboard_v1/STAGE1_ENTRYPOINT_COMPARATIVE_AUDIT_CURRENT.md](artifacts/telegram_real_mainline_v1/dashboard_v1/STAGE1_ENTRYPOINT_COMPARATIVE_AUDIT_CURRENT.md)
- [artifacts/telegram_real_mainline_v1/dashboard_v1/ARTIFACT_MANIFEST_CURRENT.md](artifacts/telegram_real_mainline_v1/dashboard_v1/ARTIFACT_MANIFEST_CURRENT.md)

## 历史与详细证据入口

- 需要看 repo 级总体 phase / layer / evidence / next action 时，先看 [docs/PROGRAM_STATE_UNIFIED.yaml](docs/PROGRAM_STATE_UNIFIED.yaml) 与 [docs/STATUS.md](docs/STATUS.md)
- 需要看“目前整体走到哪、离当前 roadmap 终点还剩多少步”时，先看 [docs/OVERALL_PROGRESS.md](docs/OVERALL_PROGRESS.md)
- 需要看 current logic / boundary / canonical state 时，先看 [docs/CURRENT_PROJECT_LOGIC_FLOW.md](docs/CURRENT_PROJECT_LOGIC_FLOW.md)
- 需要看 closeout proof、clean-clone proof、remaining backlog 时，先看 [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- 需要看 capability registry 时，先看 [docs/CAPABILITY_REGISTRY.md](docs/CAPABILITY_REGISTRY.md)
- 需要看 acceptance chains 时，先看 [docs/ACCEPTANCE_CHAINS.md](docs/ACCEPTANCE_CHAINS.md)
- 需要看 `/flow` 可见脚本时，先看 [docs/EXPERIENCE_SCRIPTS.md](docs/EXPERIENCE_SCRIPTS.md)
