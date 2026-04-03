# MVP14 Endogenous Drives + Self-Maintenance 执行包

```yaml
task_id: L3-20260403-MVP14-EDSM
created_at: "2026-04-03T19:30:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: observation_started
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP14_task_plan.md"
predecessor: "WP8/MVP13"
same_subject_line: true
not_parallel_track: true
scope: "WP9 / MVP14 Endogenous Drives + Self-Maintenance"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP9/MVP14` 的 formal owner 迁到 `OpenEmotion/openemotion/endogenous_drives/*`，接入正式 runtime 主链，并验证 governed self-maintenance candidate 与 formal owner writeback。

## 当前正式 owner target

- `OpenEmotion/openemotion/endogenous_drives/*`

## 当前正式主链 target

`OpenEmotion formal drive owner -> governed prioritization / maintenance candidate path -> EgoCore Governor / runtime / delivery`

## 当前锁定口径

- `MVP14` 是 `WP9`，接在 `WP8/MVP13` 后，不是新的主体线
- `emotiond/drives/*` 与 `drive_adapter.py` 只作为 bounded compatibility / migration reference surfaces，不是 formal owner
- `drive_homeostasis.py` / `homeostasis.py` 目前只作为测量/参考输入面，不是 formal drive owner
- `WP8` 保持 `maintenance_mode`
- `WP8` 新增样本只进 [MAINTENANCE_LEDGER.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md)，不回灌为 `WP8` scope reopen
- provider `429/401` 继续标注为外部预算层风险，不回灌为 `WP8` blocker

## 当前范围

- formal owner package
- proto-self bounded drive contract
- EgoCore runtime bridge
- legacy demotion to compatibility/reference
- paired causal validation
- controlled observation

## 当前状态

- formal owner：`implemented`
- 主链接线：`formal_owner_writeback_observed`
- 启用状态：`controlled_mainline_observation`
- 因果验证：`OpenEmotion/tests/mvp14/test_drive_behavioral_influence_formal_proof.py = 4 passed`
- 观察证据：`OpenEmotion/artifacts/mvp14/mvp14_controlled_observation_current.md = pass (V4/E4)`
- 当前 blocker：`缺重复样本，尚未达到 E5/closeout`

## 当前不做

- 放开 live autonomy
- 放开 OpenEmotion direct reply authority
- 放开 broader transport claims
- 把 `WP8` maintenance ledger 重新解释成 `WP9` readiness

## 执行入口

- authority：`Tasks/MVP14_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
