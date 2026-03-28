# SELF_AWARE_STEP_04B_self_model_authority_resolution

```yaml
task_id: SELF_AWARE_STEP_04B
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: pending
```

## real_goal

统一 `MVP13` 的 self-model authority，明确哪一条实现线才是后续 `behavioral influence` formal proof 的正式 owner，避免在 authority split 状态下继续构造伪因果证明。

## success_criteria

- 明确 `MVP13` 的正式 self-model authority 是哪条实现线
- 明确另一条线的角色：mirror / legacy / migration aid / to-be-removed
- 统一 `version spec / stage docs / main-chain wiring task / roadmap state` 的口径
- 给出后续 `behavioral influence proof` 的唯一正式入口

## authority_source

- `OpenEmotion/docs/archive/MAIN_CHAIN_WIRING_TASK.md`
- `OpenEmotion/roadmap/versions/MVP13.spec.yaml`
- `OpenEmotion/docs/mvp13/`
- `OpenEmotion/openemotion/self_model/`
- `OpenEmotion/emotiond/self_model/`
- `OpenEmotion/emotiond/self_model_adapter.py`

## current_layer

```yaml
current_layer: strategy
main_chain_status: behavioral proof blocked by authority split
```

## required_artifacts

- `OpenEmotion/roadmap/SELF_AWARE_STEP_04A_EXECUTION_REPORT_20260328.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_04A_REVIEW_20260328.md`
- `OpenEmotion/artifacts/verification/MVP13_AUDIT.md`
- `OpenEmotion/docs/archive/MAIN_CHAIN_WIRING_TASK.md`

## required_tests

- `path/existence review for all candidate authority refs`
- `contract comparison between MVP13 docs/spec and openemotion self-model schema`
- `main-chain call-path verification against emotiond/core.py`
- `independent reviewer on authority-source selection and migration risk`

## workflow_requirements

```yaml
full_spec_required: true
self_reviewer_required: true
independent_reviewer_required: true
verifier_required: true
publisher_required: true
```

## promotion_blockers

- `openemotion/self_model/*` 与 `emotiond/self_model/*` 当前不是同一 contract
- adapter 当前只是 bridge，不应升成正式语义 owner
- 在 authority 未统一前，任何 behavioral bias harness 都存在伪证明风险

## next_minimal_closure_action

先给出一份 authority-resolution 决议：保留哪条线为正式 owner、另一条线如何降级或迁移；然后再决定 `Step04C` 是否需要最小语义补足或行为影响 harness。
