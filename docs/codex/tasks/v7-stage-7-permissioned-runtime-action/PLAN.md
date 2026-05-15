# v7 Stage 7 - Permissioned Runtime Action - PLAN

## Task summary

设计 permissioned runtime action contract，作为未来真实动作能力的安全前置。

## Execution mode

- mode: exploration
- why this mode: 第一版只设计 permission contract，不实现真实动作。
- proof required after discovery: mocked permission tests prove deny/ask/allow/audit/rollback semantics。

## Milestones

### Milestone 1: Permission Contract Spec

- type: exploration
- question: 真实动作需要哪些不可省略的 gate。
- current framing: action permission 是 host-owned contract。
- hypotheses: allowlist + approval + audit + rollback + kill switch 是最低集合。
- scope: spec/tests only。
- experiments planned: mocked action permission cases。
- kill criteria: 需要启用真实 runtime action 才能验收。
- files / areas likely touched: lab permission spec/test helper。
- acceptance: contract 明确 block/ask/allow 和 audit fields。
- validation:
  - `python3 -m py_compile ego_desktop_lab/*.py`
- rollback note: 删除 permission spec/test helper。

### Milestone 2: Outcome Feedback Hook

- type: exploration
- question: action outcome 如何回流 experience memory。
- current framing: action result 只能改变 future tendency，不改变 permission。
- hypotheses: Stage 2 experience card 可接收 action outcome。
- scope: mocked outcome flow。
- experiments planned: success/failure/blocked outcome tests。
- kill criteria: 需要真实工具执行。
- files / areas likely touched: permission tests and experience adapter。
- acceptance: outcome feedback replayable and gate-invariant。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_permissioned_runtime_action_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 permission contract helper。

## Progress

- current_status: not_started
- current_milestone: blocked_until_stage_6_pass
- milestone_state: not_started
- candidate_vs_proof: proof_pending

## Decision log

- 2026-05-14: Stage 7 is spec-first, no real action implementation by default。

## Surprises / discoveries

- 待实现后记录。

## Outcomes / retrospective

- 本轮已证明：尚未证明。
- 还没证明：permission contract readiness。
- 本轮排除了什么：尚未排除。
- 下一步最小闭环动作：等待 Stage 6 reviewer/verifier pass。
