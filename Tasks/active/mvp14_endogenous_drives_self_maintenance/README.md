# MVP14 Endogenous Drives + Self-Maintenance 执行包

```yaml
task_id: L3-20260403-MVP14-EDSM
created_at: "2026-04-03T19:30:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: authority_contract_freeze
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP14_task_plan.md"
predecessor: "WP8/MVP13"
same_subject_line: true
not_parallel_track: true
scope: "WP9 / MVP14 Endogenous Drives + Self-Maintenance"
```

---

## 真实目标

先把 `WP9/MVP14` 的 authority 和 contract 写清，再开任何实现。当前只做 capability ownership、authority source、IO contract、`WP8` boundary freeze、以及 locked non-releases。

## 当前正式 owner target

- `OpenEmotion/emotiond/drives/*`

## 当前正式主链 target

`OpenEmotion formal drive owner -> governed prioritization / maintenance candidate path -> EgoCore Governor / runtime / delivery`

## 当前锁定口径

- `MVP14` 是 `WP9`，接在 `WP8/MVP13` 后，不是新的主体线
- `drive_adapter.py` 只作为 bounded compatibility surface，不是 formal owner
- `drive_homeostasis.py` / `homeostasis.py` 目前只作为测量/参考输入面，不是 formal drive owner
- `WP8` 保持 `maintenance_mode`
- `WP8` 新增样本只进 [MAINTENANCE_LEDGER.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/mvp13_persistent_self_model/MAINTENANCE_LEDGER.md)，不回灌为 `WP8` scope reopen
- provider `429/401` 继续标注为外部预算层风险，不回灌为 `WP8` blocker

## 当前范围

- capability ownership freeze
- authority source freeze
- input/output contract freeze
- `WP8` boundary freeze
- locked non-release guardrails

## 当前状态

- 代码实现：`not_started`
- 主链接线：`not_started`
- 启用状态：`not_started`
- 当前阶段只允许写 authority/contract 文档，不允许把新能力偷塞进 `WP8`

## 当前不做

- 直接实现 `MVP14` 代码
- 修改 `WP8` formal self-model owner
- 放开 live autonomy
- 放开 OpenEmotion direct reply authority
- 放开 broader transport claims

## 执行入口

- authority：`Tasks/MVP14_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
