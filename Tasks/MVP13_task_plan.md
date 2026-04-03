# MVP13 / WP8 Persistent Self-Model

> 状态：WP8 phase-detail authority
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP8`
> predecessor: `WP7/MVP12`
> same_subject_line: `true`
> legacy_mvp13_mirror_is_reference_only: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上可持久化、可审计、可重放的 formal self-model；它影响内部评估与倾向，但不获得 final reply 或 tool authority。

## Real Goal
- 把 `OpenEmotion/openemotion/self_model/*` 收成 `WP8/MVP13` 的正式 owner
- 让 self-model 可以跨 session / cycle 持续存在
- 让 self-model 的更新走受治理的 formal writeback，而不是 legacy mirror / dual-write
- 让 self-model 对 `proto_self_v2` 的影响进入同一正式主链，并保留 trace / replay / audit

## Non-Goals
- 不新开平行主体
- 不把 `MVP13` 从 MVS 主线上拆出去
- 不复活旧 `mirror / dual-write` 线为正式 owner
- 不在 `WP8 Phase 1` 引入新的 legacy 字段集作为正式 contract
- 不让 self-model 直接控制 final reply / tool execution

## Authority Source
- 顶层裁决：`Tasks/MVS_task_plan.md`
- formal owner：
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/schemas/self_model.schema.json`
- formal runtime path：
  - `EgoCore/app/runtime_v2/proto_self_runtime.py`
  - `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
  - `OpenEmotion/openemotion/proto_self_v2/*`
- reference-only：
  - `OpenEmotion/emotiond/self_model/*`
  - `OpenEmotion/emotiond/self_model_mirror.py`
  - `EgoCore/egocore/runtime/self_model_manager.py`
  - `OpenEmotion/tools/mvp13_*`
  - `OpenEmotion/artifacts/mvp13/TASK.md`

## Locked Decisions
- `proto_self_v2.state.self_model` 只作为 formal owner state 的 runtime-local projection
- formal read path：
  - owner self-model store
  - `runtime_v2 -> proto_self_runtime`
  - `UpdatePacketV2.runtime_summary.self_model_context`
  - `proto_self_v2` read-only consumption
- formal write path：
  - `self_model_delta` / `self_model_update_candidates`
  - `self_model_update_gate`
  - formal owner store writeback
- formal owner fields 仅限当前 schema：
  - `schema_version`
  - `identity_handle`
  - `capabilities`
  - `limitations`
  - `active_goals`
  - `standing_commitments`
  - `tool_authority_boundary`
  - `dependency_map`
  - `confidence_by_domain`
  - `known_unknowns`
  - `created_at`
  - `last_modified_at`
  - `modification_audit_trail`
- legacy-only 字段在 `WP8 Phase 1` 中不可作为 formal proof levers

## Milestones
1. `T00` Authority Freeze
2. `T10` Owner Contract Convergence
3. `T20` Persistence / Audit / Replay
4. `T30` Identity Invariants / Drift Governance
5. `T40` Proto-Self Read Integration
6. `T50` Governed Writeback
7. `T60` EgoCore Bridge
8. `T70` Evidence / Acceptance
9. `T80` Subagent Assignment

## Current Phase Status
- `T00/T10/T20/T30/T40/T50/T60/T70/T80` 已完成，且已通过 `scenario bank + batch controlled observation runner` 拿到 controlled `E5` formal owner writeback 稳定样本集
- 当前层级：`closure`
- 当前 blocker：`controlled observation` 范围内无主 blocker；provider `429/401` 仅记为外部预算层风险；live autonomy / transport evidence 仍不在 `WP8` scope
- 当前最小闭环动作：将 `WP8` 置为维护态并把后续样本写入 `Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md`；若继续推进主线，先定义 `WP9/MVP14` authority，而不是继续扩 `WP8`

## Success Criteria
- 文档层：
  - 所有 authority / contract / gate / proof levers 冻结
  - 所有 subtask cards subagent-ready
- 实现层后续准入：
  - persistence 可用
  - replay 可重放
  - invariant / drift gate 成立
  - self-model 进入 formal read/write 主链
  - proof 只依赖 formal owner fields

## Completion Rules
- 本文件完成不等于 `MVP13` 完成
- 只有实现、验证、E4 样本到位后，才可宣称 `WP8` 生效
- 达到 `E5` 后，仍不得把 controlled observation 等同于 live autonomous authority
- `WP8` 达到 controlled `E5` 后，可宣称本阶段在 formal owner / controlled observation 轴上收口，并转入维护态
- 维护态期间新增样本只进入 maintenance ledger，除非触发明确 reopen 条件
