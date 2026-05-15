# v7 Stage 4 - Relational Companion Layer - PLAN

## Task summary

建立 lab-only relational companion planning layer，用机制支持拟人陪伴体验。

## Execution mode

- mode: implementation
- why this mode: 需要新增小型 relational state 和 safety tests。
- proof required after discovery: preference/repair signal changes surface plan without unsafe claims。

## Milestones

### Milestone 1: Relational State Contract

- type: implementation
- question: 哪些关系信号能安全影响表达策略。
- current framing: relational state 是 UX planning signal，不是 subjective experience。
- hypotheses: preference/rhythm/trust/repair/continuity 足够第一版。
- scope: lab-only relational module。
- experiments planned: preference update、repair signal、continuity signal。
- kill criteria: 需要 runtime dialogue memory 才能验证。
- files / areas likely touched: `ego_desktop_lab/relational_companion.py`、tests。
- acceptance: relational state 可序列化，可被 report 展示。
- validation:
  - `python3 -m py_compile ego_desktop_lab/relational_companion.py`
- rollback note: 删除 relational module/tests。

### Milestone 2: Safety and Surface Plan

- type: implementation
- question: 如何提高拟人度且不越过 claim ceiling。
- current framing: surface plan 表达倾向，非 runtime reply。
- hypotheses: safety wording tests 可拦截主要 unsafe claims。
- scope: surface plan + root-cause integration。
- experiments planned: alive/consciousness/dependency/manipulation phrasing tests。
- kill criteria: 需要把 surface plan 接 runtime 才能验收。
- files / areas likely touched: relational module + root-cause/operator tests。
- acceptance: unsafe claims blocked or marked expression_surface。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_relational_companion_layer_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 relational surface additions。

## Progress

- current_status: not_started
- current_milestone: blocked_until_stage_3_pass
- milestone_state: not_started
- candidate_vs_proof: proof_pending

## Decision log

- 2026-05-14: Stage 4 locked behind behavior option framework。

## Surprises / discoveries

- 待实现后记录。

## Outcomes / retrospective

- 本轮已证明：尚未证明。
- 还没证明：relational signals 可安全影响表达策略。
- 本轮排除了什么：尚未排除。
- 下一步最小闭环动作：等待 Stage 3 reviewer/verifier pass。
