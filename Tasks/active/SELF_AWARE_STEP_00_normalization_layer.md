# SELF_AWARE_STEP_00_normalization_layer

```yaml
task_id: SELF_AWARE_STEP_00
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: spec_ready
```

## real_goal

建立唯一主判定层，统一长期阶段层、`OE_MVP`、`SELF_WS`、`EG_PHASE`、状态词表、证据等级、验证等级与准入口径。

## success_criteria

- `SELF_AWARE_NORMALIZATION_RULES_20260328.md` 落盘
- 定义权威优先级与冲突裁决顺序
- 给出阶段映射表与状态词典
- 给出当前正式判定模板

## authority_source

- `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
- `OpenEmotion/roadmap/ROADMAP_STATE.json`
- `OpenEmotion/roadmap/ROADMAP_INDEX.md`

## current_layer

```yaml
current_layer: representation
main_chain_status: 接入
```

## required_artifacts

- `OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`
- `OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md`

## required_tests

- 逐条核对主判定优先级是否能裁决 `blocked` vs `shadow_running`
- 检查一个阶段是否只保留一个当前正式状态

## promotion_blockers

- 权威优先级未定
- 阶段轴混用
- `ROADMAP_INDEX` 仍指向断链文档

## next_minimal_closure_action

用统一编译层重算当前阶段与当前 blocker，形成 Step 01。

