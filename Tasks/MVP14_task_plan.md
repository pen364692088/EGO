# MVP14 / WP9 Endogenous Drives + Self-Maintenance

> 状态：WP9 authority/contract freeze
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
- 不把旧 `drive_adapter / drive_homeostasis / homeostasis` 直接升格为 formal owner
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
  - `OpenEmotion/emotiond/drives/*`
- `OpenEmotion/emotiond/drive_adapter.py` 只作为 bounded compatibility / replay-friendly access surface
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
- Allowed outputs:
  - `drive_state_snapshot`
  - `priority_snapshot`
  - `maintenance_request_candidates`
  - `candidate_bias_terms`
  - `drive_audit_entries`
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
- 当前层级：`strategy`
- 当前状态：`authority_contract_freeze_only`
- 当前 blocker：`MVP14` 代码实现未开始，这是本阶段刻意冻结，不是阻塞故障
- 当前最小闭环动作：完成 capability ownership / authority source / IO contract / WP8 boundary / non-release guardrails 文档包

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
- 本文件完成不等于 `MVP14` 实现开始
- 本文件完成不等于 `MVP14` 已接主链
- 只有 authority / contract 冻结后，才允许选第一张 `WP9` 实现卡
