# MVP20 Subagent Assignment

## 规则

- 所有 subagent 任务都以 `Tasks/MVS_task_plan.md` 为 parent authority
- 所有 subagent 任务都以 `Tasks/MVP20_task_plan.md` 为 phase-detail authority
- 不允许 subagent 自行扩 scope 到 `WP16+`
- 不允许 subagent 把 `WP7` host proactive substrate 或 `WP8~WP14` upstream owner surfaces 升格为 `WP15` formal owner path
- `WP7~WP14` 当前都保持 maintenance / frozen upstreams；本文件只同步任务分派与 write scope，不 reopen upstream

## 冻结的初始分派

| Worker | Tasks | 可并行 | 写入范围 |
|--------|-------|--------|----------|
| docs worker | `T00/T40/T80/T90` | 部分可并行 | `Tasks/*`, legacy register, closeout docs, `PROJECT_MEMORY.md`, verifier docs |
| OpenEmotion owner worker | `T10` | 否 | `OpenEmotion/openemotion/initiative_self/*`, owner infra tests |
| proto_self worker | `T20` | 否 | `OpenEmotion/openemotion/proto_self_v2/*`, proto-self integration tests |
| EgoCore worker | `T30` | 否 | `EgoCore/app/runtime_v2/*`, `EgoCore/app/openemotion_adapter/*`, runtime bridge tests |
| proof/observation worker | `T50/T60/T70` | 顺序推进 | causal proof tools/tests/artifacts, controlled observation tools/tests/artifacts, scenario bank |

## 任务表

| Task | Repo Owner | 可并行 | 写入范围 |
|------|------------|--------|----------|
| `T00_AUTHORITY_FREEZE` | Tasks/docs | 否 | `Tasks/MVS_task_plan.md`, `Tasks/MVP20_task_plan.md`, execution pack docs, `PROJECT_MEMORY.md` |
| `T10_FORMAL_OWNER_PACKAGE` | OpenEmotion | 否 | `OpenEmotion/openemotion/initiative_self/*`, `OpenEmotion/tests/mvp20/test_initiative_owner_infra.py` |
| `T20_PROTO_SELF_CONTRACT_INTEGRATION` | OpenEmotion | 否 | `OpenEmotion/openemotion/proto_self_v2/*`, `OpenEmotion/tests/mvp20/test_initiative_proto_self_integration.py` |
| `T30_EGOCORE_RUNTIME_BRIDGE` | EgoCore | 否 | `EgoCore/app/runtime_v2/*`, `EgoCore/app/openemotion_adapter/*`, EgoCore tests |
| `T40_LEGACY_DEMOTION_AND_COMPAT_MAP` | Tasks/docs + Dual-repo verifier | 是 | reference docs, `OpenEmotion/tools/verify_mvp20_mainline_wiring.py`, demotion tests, legacy register |
| `T50_CAUSAL_VALIDATION` | Dual-repo | 否 | `OpenEmotion/tests/mvp20/*`, proof tools/artifacts |
| `T60_CONTROLLED_OBSERVATION_SINGLE` | Dual-repo | 否 | `OpenEmotion/tools/*`, `OpenEmotion/artifacts/mvp20/*`, observation tests |
| `T70_BATCH_OBSERVATION_AND_AGGREGATE` | Dual-repo | 否 | `OpenEmotion/scenarios/mvp20_observation_bank/*`, batch tools, aggregate artifacts/tests |
| `T80_CLOSEOUT_AND_QA_BASELINE` | Tasks/docs | 否 | `Tasks/active/mvp20_host_governed_initiative_continuity/*`, `Tasks/MVP20_task_plan.md`, `PROJECT_MEMORY.md`, `OpenEmotion/artifacts/mvp20/MVP20_COMPLETION_CURRENT.*` |
| `T90_SUBAGENT_ASSIGNMENT` | Tasks/docs | 否 | `SUBAGENT_ASSIGNMENT.md` |

## 固定依赖

- `T00 -> T10 -> T20 -> T30 -> T50 -> T60 -> T70 -> T80`
- `T40` 依赖 `T00`，可在 `T10` 完成后与 `T20/T30` 的文档 / verifier 准备并行
- `T90` 依赖 `T00`，用于同步当前 authority package 的分派表；在 package 已收口时允许 no-op 验收

## 交付要求

每个 subagent 交付必须包含：

- 写入文件列表
- 验证命令
- 完成标准是否满足
- 未证明项
- 回退点
