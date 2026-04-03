# MVP13 Persistent Self-Model 执行包

```yaml
task_id: L3-20260402-MVP13-PSM
created_at: "2026-04-02T22:10:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: observation_ready
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP13_task_plan.md"
predecessor: "WP7/MVP12"
same_subject_line: true
not_parallel_track: true
scope: "WP8 / MVP13 Persistent Self-Model"
```

---

## 真实目标

为同一个主体补上 formal persistent self-model，使其能跨 session / cycle 持续存在，并通过正式主链影响内部评估，而不越权获得 final reply / tool authority。

## 当前正式 owner

- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/schemas/self_model.schema.json`

## 当前正式主链

`runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`

## 当前锁定口径

- `MVP13` 是 `WP8`，是 `WP7/MVP12` 之后的下一阶段
- `proto_self_v2.state.self_model` 只是 formal owner state 的 runtime-local projection
- 读路径：
  - owner store
  - `UpdatePacketV2.runtime_summary.self_model_context`
  - `proto_self_v2` read-only consumption
- 写路径：
  - `self_model_delta` / `self_model_update_candidates`
  - `self_model_update_gate`
  - formal owner store writeback
- 不得重新启用旧 `mirror / dual-write` 作为 formal owner path

## 当前范围

- authority freeze
- owner contract
- persistence / audit / replay contract
- invariants / drift contract
- proto-self read integration contract
- governed writeback contract
- bridge and evidence task split

## 当前实现状态

- `T10` formal owner contract 已收敛
- `T20` persistence / audit / replay 已落 formal owner path
- `T30` identity invariants / drift governance 已落 formal gate
- `T40` proto-self read integration 已接 `runtime_summary.self_model_context`
- `T50` governed writeback 已落 formal owner gate
- `T60` EgoCore bridge 已把 formal owner context / writeback result 接回 runtime 主链
- `T70` 本地证据包已生成：
  - `OpenEmotion/artifacts/mvp13/mvp13_local_evidence_current.md`

## 当前 blocker

- 还没有真实 `E4` mainline-trigger self-model writeback 样本
- 当前只能报 `E3 local proof`, 不能报 `E4` 或 `E5`

## 本轮不做

- 直接实现 `MVP13` 代码
- 迁移 legacy self-model 整套结构
- 修改 Governor authority
- 放开 live autonomy

## 执行入口

- authority：`Tasks/MVP13_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- subagent 说明：`SUBAGENT_ASSIGNMENT.md`
- task cards：`cards/`
