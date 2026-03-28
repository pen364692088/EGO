# SELF_AWARE_STEP_04F_behavioral_influence_formal_proof

```yaml
task_id: SELF_AWARE_STEP_04F
created_at: "2026-03-29T03:15:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: pending
```

## real_goal

在已建立的 formal-owner-backed decision surface 上，完成一条受治理、可 replay、可比较的 `behavioral influence` formal proof，证明 `openemotion/self_model/*` 的受控字段干预会改变至少一个真实下游决策点。

## success_criteria

- 存在一条唯一正式 proof path，消费 `openemotion/self_model/*` 的 authoritative 字段
- paired intervention/control 样本能稳定改变同一主链 decision point
- proof 不依赖 legacy-only `emotiond/self_model/*` 字段
- governor / sandbox / replay discipline 保持成立

## authority_source

- `OpenEmotion/roadmap/SELF_AWARE_STEP_04E_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/openemotion/self_model/model.py`
- `OpenEmotion/emotiond/self_model_adapter.py`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/docs/mvp13/MVP13_EXIT_CRITERIA.md`
- `OpenEmotion/roadmap/versions/MVP13.spec.yaml`

## current_layer

```yaml
current_layer: verification
main_chain_status: formal owner contract converged; owner-backed decision surface established; behavioral influence proof pending
```

## required_artifacts

- `OpenEmotion/roadmap/SELF_AWARE_STEP_04E_EXECUTION_REPORT_20260329.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_04E_REVIEW_20260329.md`
- `OpenEmotion/docs/mvp13/SELF_MODEL_STATE_SCHEMA.md`

## required_tests

- `pytest -q OpenEmotion/tests/mvp13/test_owner_backed_decision_surface.py`
- `paired intervention/control harness with real mainline call path`
- `independent reviewer on authority and overreach risk`
- `git diff --check`

## workflow_requirements

```yaml
full_spec_required: true
self_reviewer_required: true
independent_reviewer_required: true
verifier_required: true
publisher_required: true
```

## promotion_blockers

- E4 behavioral influence 证据尚未建立
- downstream decision change 还未形成 paired intervention/control 证据链
- MVP13 stage pass 仍未满足 `behavioral_influence_e4_proven`

## next_minimal_closure_action

先定义一条最小 paired harness：固定 base scores、干预 `confidence_by_domain["action:<action>"]`、比较同一 target 上的主链 action selection 变化。
