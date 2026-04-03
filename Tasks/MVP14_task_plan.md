# MVP14 / WP9 Endogenous Drives + Self-Maintenance

> 状态：WP9 controlled observation started
> parent_authority: `Tasks/MVS_task_plan.md`
> phase: `WP9`
> predecessor: `WP8/MVP13`
> same_subject_line: `true`
> not_parallel_track: `true`
> wp8_boundary_frozen: `true`

## 一句话主线
在同一条 MVS 主线里，为同一个主体补上 endogenous drives 与 self-maintenance capability；它们只作为受治理的内部压力、优先级和维护候选来源，不获得 final reply、tool execution 或 transport authority。

## Real Goal
- 冻结 `WP9/MVP14` 的 capability ownership
- 冻结 `WP9/MVP14` 的 authority source
- 冻结 `WP9/MVP14` 的 input / output contract
- 冻结 `WP8` 向 `WP9` 的边界，不让 `WP9` 反向改写 `WP8`
- 明确当前仍然不放开的能力，防止“`WP8 pass` => authority 扩张”的错误升级

## Non-Goals
- 不直接实现 `MVP14` 代码
- 不把新能力塞回 `WP8`
- 不把旧 `emotiond/drives / drive_adapter / drive_homeostasis / homeostasis` 直接升格为 formal owner
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims

## Authority Source
- 顶层裁决：
  - `Tasks/MVS_task_plan.md`
- `WP9` phase-detail authority：
  - `Tasks/MVP14_task_plan.md`
- version spec：
  - `OpenEmotion/roadmap/versions/MVP14.spec.yaml`
- technical reference：
  - `OpenEmotion/docs/mvp14/MVP14_STAGE_OVERVIEW.md`
  - `OpenEmotion/docs/mvp14/ENDOGENOUS_DRIVES_ARCHITECTURE.md`
  - `OpenEmotion/docs/mvp14/DRIVE_STATE_SCHEMA.md`
  - `OpenEmotion/docs/mvp14/DRIVE_GOVERNANCE_AND_PRIORITY_POLICY.md`
  - `OpenEmotion/docs/mvp14/SELF_MAINTENANCE_RUNTIME.md`

## Locked Decisions
- `WP9/MVP14` 仍属于同一条 MVS 主线，不是新的主体线
- formal owner target 固定为：
  - `OpenEmotion/openemotion/endogenous_drives/*`
- `OpenEmotion/emotiond/drives/*`、`OpenEmotion/emotiond/drive_adapter.py` 只作为 bounded compatibility / migration / replay-friendly reference surfaces
- `OpenEmotion/emotiond/drive_homeostasis.py` 与 `OpenEmotion/emotiond/homeostasis.py` 只作为测量/参考/输入表面；在 `WP9` 第一刀中不升格为 formal drive owner
- `WP8` formal self-model owner 继续固定为：
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/schemas/self_model.schema.json`
- `WP9` 不得改变 `WP8` 的 formal read/write path、controlled `E5` 口径、或 maintenance_mode 状态
- `WP9` 的输出只能进入 governed prioritization / maintenance candidate path，不能直接控制 final reply / tool execution / transport

## Capability Ownership
- OpenEmotion owns:
  - endogenous drive state
  - drive accumulation / decay / competition
  - homeostatic deviation interpretation
  - maintenance debt interpretation
  - governed maintenance candidate generation
  - drive audit / replayable state transitions
  - formal owner package: `OpenEmotion/openemotion/endogenous_drives/*`
- EgoCore owns:
  - runtime scheduling
  - Governor / approval / delivery / transport
  - final reply authority
  - tool execution authority
  - external channel claims
- `proto_self_v2` owns:
  - bounded consumption of drive context
  - bounded emission of downstream weighting or maintenance candidate hooks
  - it does not own drive state itself

## IO Contract Freeze
- Allowed inputs:
  - `WP8` self-model projection
  - developmental tensions / unresolved contradictions
  - continuity break signals
  - replay inconsistency / maintenance debt / drift markers
  - bounded homeostatic measurements
  - long-horizon unfinished-goal pressure
  - `runtime_summary.idle_window`
  - `runtime_summary.recent_delivery_outcome`
  - `runtime_summary.resource_budget_hint`
  - `runtime_summary.maintenance_context`
- Allowed outputs:
  - `endogenous_drive_delta`
  - `drive_state_snapshot`
  - `priority_snapshot`
  - `self_maintenance_candidate`
  - `candidate_bias_terms`
  - `drive_audit_entries`
  - `trace_payload.drive_context`
- Forbidden outputs:
  - final reply text
  - tool command
  - direct transport instruction
  - authority escalation
  - ungoverned writeback into `WP8` formal owner state

## WP8 Boundary Freeze
- `WP8` stays `maintenance_mode`
- new `WP8` samples go only to `Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md`
- provider `429/401` remains an external budget risk unless it causes formal owner writeback regression
- `WP9` may consume `WP8` outputs only through frozen read surfaces
- `WP9` may not reinterpret `WP8 controlled E5` as live authority or broader transport maturity

## Current Phase Status
- 当前层级：`verification`
- 当前状态：`formal owner mainline wired; first controlled observation pass`
- 当前 blocker：`缺重复 controlled observation 样本，尚未达到 E5 / closeout`
- 当前最小闭环动作：继续收集 `WP9` formal owner writeback + governed maintenance candidate 的受控样本

## Current Proven State
- `OpenEmotion/openemotion/endogenous_drives/*` 已成为 `WP9` formal owner package
- `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2` 已能读 bounded drive projection，并把 `endogenous_drive_delta / endogenous_drive_writeback / self_maintenance_candidate` 挂回宿主上下文
- `emotiond/drives/*` 已降级为 compatibility/reference surface，不再作为 formal owner
- paired causal proof 已通过：
  - `OpenEmotion/tests/mvp14/test_drive_behavioral_influence_formal_proof.py = 4 passed`
- 首个 controlled observation 已通过：
  - `OpenEmotion/artifacts/mvp14/mvp14_controlled_observation_current.md`
  - 结果：`status = pass`、`verification_level = V4`、`evidence_level = E4`、`gate_verdict = allow_writeback`、`maintenance_candidate_present = true`、`replay_valid = true`

## Success Criteria
- `Tasks/MVS_task_plan.md` 中已正式出现 `WP9: Endogenous Drives + Self-Maintenance`
- `Tasks/active/mvp14_endogenous_drives_self_maintenance/` 已存在且口径一致
- 文档已锁死：
  - capability ownership
  - authority source
  - input/output contract
  - `WP8` boundary freeze
  - locked non-releases
- 文档没有把 `WP8` 的轴内 `E5` 冒充为 `WP9` readiness 或全局成熟

## Completion Rules
- 首个 controlled observation `V4/E4` 不等于 `WP9` 已稳定通过
- 未达到重复样本 `E5` 前，不得宣称 `WP9` 稳定解决或可收口
- `WP9` 的 `V4/E4` 不得被解释为 live autonomy、OpenEmotion direct reply authority、或 broader transport maturity
