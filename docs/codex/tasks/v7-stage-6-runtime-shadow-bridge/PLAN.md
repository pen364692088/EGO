# v7 Stage 6 - Runtime Shadow Bridge - PLAN

## Task summary

实现 lab-only runtime shadow bridge，用 copied event summary 做观察和 root-cause diagnostics。

## Execution mode

- mode: implementation
- why this mode: shadow tap contract 已有文档，需要测试化实现。
- proof required after discovery: shadow report compares decisions without mutation。

## Milestones

### Milestone 1: Shadow Event Contract

- type: implementation
- question: copied runtime event 最小字段是什么。
- current framing: shadow bridge 只观察，不接管。
- hypotheses: event summary 可包含 input, runtime decision, delivery status, trace refs。
- scope: lab-only shadow module。
- experiments planned: normal event、expression mismatch、listener proof mismatch。
- kill criteria: 需要读真实 runtime logs 才能验收。
- files / areas likely touched: `ego_desktop_lab/runtime_shadow_bridge.py`、tests。
- acceptance: event summary 可生成 shadow report。
- validation:
  - `python3 -m py_compile ego_desktop_lab/runtime_shadow_bridge.py`
- rollback note: 删除 shadow module/tests。

### Milestone 2: Mismatch Root-Cause

- type: implementation
- question: runtime/lab mismatch 是否能归因。
- current framing: mismatch 是诊断，不是 authority conflict。
- hypotheses: root-cause categories 覆盖第一版 mismatch。
- scope: root-cause integration。
- experiments planned: runtime_bridge / expression_surface / evidence_claim_mismatch。
- kill criteria: 需要写 formal ledger 才能验收。
- files / areas likely touched: shadow module + tests。
- acceptance: mismatch report 不提升 evidence claim。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_runtime_shadow_bridge_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 shadow bridge。

## Progress

- current_status: not_started
- current_milestone: blocked_until_stage_5_pass
- milestone_state: not_started
- candidate_vs_proof: proof_pending

## Decision log

- 2026-05-14: Runtime bridge is shadow-only and locked behind lab skill proof。

## Surprises / discoveries

- 待实现后记录。

## Outcomes / retrospective

- 本轮已证明：尚未证明。
- 还没证明：runtime shadow diagnostics。
- 本轮排除了什么：尚未排除。
- 下一步最小闭环动作：等待 Stage 5 reviewer/verifier pass。
