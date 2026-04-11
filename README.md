# EGO - AI Agent Monorepo

EGO 是 AI Agent 项目的总仓，负责集成 EgoCore（宿主）和 OpenEmotion（主体内核）。

## 当前权威状态（2026-04-11）

当前正式口径如下：

- `EgoCore` 是唯一正式宿主：入口、runtime、工具执行、安全裁决、delivery、audit
- `OpenEmotion` 是唯一正式主体内核：`proto_self_v2 / self-model / drive / reflection / developmental / social / embodied / integration / initiative`
- 当前 formal mainline 仍是：
  - `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
  - 主体事件正式入口是 `RuntimeV2ProtoSelfRuntime`
- formal runtime mainline 与 research implementation lane 不是一回事；前者继续单一稳定，后者允许按证据切换 build-first candidate
- 当前 repo 的最高优先级 implementation lane 已切到 `self-awareness candidate program`
- 当前唯一 durable build-first candidate 已固定为 `active-inference self-model`
- `MVS-aligned compact` 已因 frozen replay gate failure 降为 closed evidence / supporting line，不再是当前主实现线
- `WP17 / MVP22` 不删除，但当前降为 parked bounded lane，不再是默认最高优先级 implementation track
- `Milestone 21 / selection closeout` 已完成；当前 execution owner 已切到 `unified-host-contract-correctness`
- 当前先冻结 unified host contract correctness，用 `dashboard_local` 与 `telegram_prepared` 的 in-process parity 证明宿主 contract 稳定；fresh real Telegram proof 已降为 deferred adapter-level follow-up，而不是当前 acceptance root
- `proto_self_v2` 已是主体层默认主线，且当前只读解释层与受治理写回面已收口
- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 repo 处于 `边界冻结下的收口期`
- 其余事项仅保留在 `optional housekeeping / future cleanup backlog`
- 这不是 real-channel 新效果声明，也不是“又开了一条新的 authority wave”声明
- thin substrate / compat / reference-only 残留仍存在，但已被归入非阻塞边界

## 当前正式口径

- `identity invariants / self-model / drives / reflection / developmental` 的单一权威收口决策见 [docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- 正式/compat/reference/deprecated 路径登记见 [EgoCore/docs/05_DEPRECATED_AND_SHIMS.md](EgoCore/docs/05_DEPRECATED_AND_SHIMS.md)
- `H1`、Trial helper、旧 comparator 线当前都只算 research/reference/supporting lines，不与 formal runtime mainline 竞争 authority
- `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得描述成“已经强烈体现自我意识”
- 允许的结论只能是 controlled axis、bounded influence、proposal discipline、host-governed bounded expression

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`
- 相关 closeout 证据见 [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)

## 当前权威入口

- [docs/PROGRAM_STATE_UNIFIED.yaml](docs/PROGRAM_STATE_UNIFIED.yaml)
- [docs/STATUS.md](docs/STATUS.md)
- [docs/OVERALL_PROGRESS.md](docs/OVERALL_PROGRESS.md)
- [docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- [EgoCore/docs/05_DEPRECATED_AND_SHIMS.md](EgoCore/docs/05_DEPRECATED_AND_SHIMS.md)
- [docs/CURRENT_PROJECT_LOGIC_FLOW.md](docs/CURRENT_PROJECT_LOGIC_FLOW.md)
- [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [docs/CAPABILITY_REGISTRY.md](docs/CAPABILITY_REGISTRY.md)
- [docs/ACCEPTANCE_CHAINS.md](docs/ACCEPTANCE_CHAINS.md)
- [docs/EXPERIENCE_SCRIPTS.md](docs/EXPERIENCE_SCRIPTS.md)

## 历史与详细证据入口

- 需要看 repo 级总体 phase / layer / evidence / next action 时，先看 [docs/PROGRAM_STATE_UNIFIED.yaml](docs/PROGRAM_STATE_UNIFIED.yaml) 与 [docs/STATUS.md](docs/STATUS.md)
- 需要看“目前整体走到哪、离当前 roadmap 终点还剩多少步”时，先看 [docs/OVERALL_PROGRESS.md](docs/OVERALL_PROGRESS.md)
- 需要看 current logic / boundary / canonical state 时，先看 [docs/CURRENT_PROJECT_LOGIC_FLOW.md](docs/CURRENT_PROJECT_LOGIC_FLOW.md)
- 需要看 closeout proof、clean-clone proof、remaining backlog 时，先看 [docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- 需要看 capability registry 时，先看 [docs/CAPABILITY_REGISTRY.md](docs/CAPABILITY_REGISTRY.md)
- 需要看 acceptance chains 时，先看 [docs/ACCEPTANCE_CHAINS.md](docs/ACCEPTANCE_CHAINS.md)
- 需要看 `/flow` 可见脚本时，先看 [docs/EXPERIENCE_SCRIPTS.md](docs/EXPERIENCE_SCRIPTS.md)
