# SELF_AWARE_STEP_01_current_state_recompute

```yaml
task_id: SELF_AWARE_STEP_01
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: spec_ready
```

## real_goal

基于统一编译层重算当前真实位置，明确当前长期阶段、当前执行版本、当前 proven floor、当前 provisional ceiling 与 blocker。

## success_criteria

- 当前长期阶段有唯一结论
- 当前执行版本与执行状态有唯一结论
- 明确 `blocked` 的正式含义
- 把 handoff 的乐观表述降级为历史说明而非当前裁决

## authority_source

- `OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`
- `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
- `OpenEmotion/roadmap/ROADMAP_STATE.json`
- `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`

## current_layer

```yaml
current_layer: strategy
main_chain_status: 接入
```

## required_artifacts

- 当前阶段重算报告
- proven floor / provisional ceiling 对照表

## required_tests

- 检查 `ROADMAP_STATE` 与 `LATEST_HANDOFF` 冲突时是否统一输出保守判定
- 检查 `MVP16 blocked` 是否仍保留为当前正式状态

## promotion_blockers

- 版本 spec 尚未补齐
- `MVP12-15` formal proof 判据未固化

## next_minimal_closure_action

补齐 `MVP12-16` 版本 spec，结束“有阶段叙述但缺机器可执行 contract”的状态。

