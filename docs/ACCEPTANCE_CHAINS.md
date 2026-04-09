# Acceptance Chains

本文件是 runner 索引，不是新的 authority source。

## 当前权威状态（2026-04-09）

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 这是 repo/integration scope closeout，不是 real-channel 新效果声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`

## 当前正式口径

- 本文件只索引 acceptance runners 与当前报告，不升格为 authority source
- current report 只作为当前验证层入口，不代表额外的主权威
- 相关 closeout / current logic / capability registry 入口见：
  - [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
  - [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
  - [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`

## 当前权威入口

- [PROGRAM_STATE_UNIFIED.yaml](PROGRAM_STATE_UNIFIED.yaml)
- [STATUS.md](STATUS.md)
- [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
- [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
- [EXPERIENCE_SCRIPTS.md](EXPERIENCE_SCRIPTS.md)

## 历史与详细证据入口

- 下方链表保留为 runner 索引与验证摘要，不是新的 authority source
- 具体 current report、command、proves / does not prove 仍以表格为准

## 第 0 链

| chain | command | current report | proves | does not prove |
|---|---|---|---|---|
| subject ingress mainline | `python3 scripts/codex/run_acceptance_subject_ingress_mainline.py` | `artifacts/acceptance_chains/SUBJECT_INGRESS_MAINLINE_CURRENT.md` | 已授权 turn 是否先经过主体、host-only 与 degraded 是否分离 | 其他能力已经完整体验化 |

## 五条正式能力链

| chain | command | current report | proves | does not prove |
|---|---|---|---|---|
| continuity | `python3 scripts/codex/run_acceptance_continuity.py` | `artifacts/acceptance_chains/ACCEPTANCE_CONTINUITY_CURRENT.md` | same-session / cross-session / cross-day 当前状态 | continuity 本身等于强前台主观体验 |
| self-model causality | `python3 scripts/codex/run_acceptance_self_model_causality.py` | `artifacts/acceptance_chains/ACCEPTANCE_SELF_MODEL_CAUSALITY_CURRENT.md` | self-model 在 controlled axis 上的因果影响 | direct authority / unrestricted autonomy |
| drives causality | `python3 scripts/codex/run_acceptance_drives_causality.py` | `artifacts/acceptance_chains/ACCEPTANCE_DRIVES_CAUSALITY_CURRENT.md` | drives 对 candidate / tendency 的 bounded 因果影响 | live autonomy / direct transport authority |
| reflection boundary | `python3 scripts/codex/run_acceptance_reflection_boundary.py` | `artifacts/acceptance_chains/ACCEPTANCE_REFLECTION_BOUNDARY_CURRENT.md` | reflection writeback + proposal-only 边界 | reflection 可直接说话或执行 |
| developmental / proactive | `python3 scripts/codex/run_acceptance_developmental_proactive.py` | `artifacts/acceptance_chains/ACCEPTANCE_DEVELOPMENTAL_PROACTIVE_CURRENT.md` | developmental continuity + host-governed proactive slice | global proactive enablement / unsolicited autonomy |
