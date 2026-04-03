# MVP13 Persistent Self-Model 执行包

```yaml
task_id: L3-20260402-MVP13-PSM
created_at: "2026-04-02T22:10:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: maintenance_mode
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
- 第一条 controlled mainline writeback 观察样本已生成：
  - `OpenEmotion/artifacts/mvp13/mvp13_controlled_observation_current.md`
- scenario bank controlled batch report 已生成：
  - `OpenEmotion/artifacts/mvp13/mvp13_controlled_observation_batch_current.md`
- formal closure report 已生成：
  - `OpenEmotion/artifacts/mvp13/MVP13_COMPLETION_CURRENT.md`
- maintenance ledger 已建立：
  - `Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md`

## 当前 blocker

- `controlled observation` 范围内已无主 blocker
- 残余风险：
  - chat provider 在 batch 运行时可能出现 transient `429/401`
  - 这不影响当前 formal owner writeback `E5` 口径，但会影响后续重复运行的稳定性预算
- 当前状态：
  - `WP8` 已可收口进入维护态
  - 新增样本只进入 maintenance ledger，不自动 reopen `WP8`
  - 若继续推进主线，应先定义 `WP9/MVP14` authority / contract

## 本轮不做

- 直接实现 `MVP13` 代码
- 迁移 legacy self-model 整套结构
- 修改 Governor authority
- 放开 live autonomy

## 执行入口

- authority：`Tasks/MVP13_task_plan.md`
- status：`STATUS.md`
- maintenance ledger：`MAINTENANCE_LEDGER.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- subagent 说明：`SUBAGENT_ASSIGNMENT.md`
- task cards：`cards/`
- scenario bank：`OpenEmotion/scenarios/mvp13_observation_bank/`
- batch runner：`OpenEmotion/tools/run_mvp13_controlled_observation_batch.py`
