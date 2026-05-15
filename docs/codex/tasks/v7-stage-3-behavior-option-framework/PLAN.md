# v7 Stage 3 - Behavior Option Framework - PLAN

## Task summary

建立 lab-only registered behavior option framework，支持 primitive / skill_option / plan_option 竞争。

## Execution mode

- mode: implementation
- why this mode: 现有 behavior option 可扩展为 registry contract。
- proof required after discovery: unregistered cannot select, gate invariance, deterministic ranking。

## Milestones

### Milestone 1: Option Registry Contract

- type: implementation
- question: option contract 如何避免与 intention specs 分叉。
- current framing: registry 是 intention 的审计面，不是第二套 policy。
- hypotheses: registry 可从现有 specs 派生。
- scope: `ego_desktop_lab/behavior_options.py`。
- experiments planned: registered/unregistered/high-risk option tests。
- kill criteria: 需要复制 policy scoring 才能实现 registry。
- files / areas likely touched: behavior options + tests。
- acceptance: option 包含 affordance/allowed_actions/effect/risk/cost/permission/rollback。
- validation:
  - `python3 -m py_compile ego_desktop_lab/behavior_options.py`
- rollback note: 回退 registry 扩展。
- state: local_pass
- result: registered behavior option contract is now exposed with allowed-action compatibility checks, without changing policy ranking, gate ownership, tool permissions, scheduler, runtime bridge, or LLM planner behavior.

### Milestone 2: Kernel Selection Restriction

- type: implementation
- question: kernel 是否只选择 registered option。
- current framing: option framework 必须约束选择入口。
- hypotheses: selected intention 可映射到 registered option。
- scope: agency kernel selection side。
- experiments planned: 注入 unregistered option，确认不被选。
- kill criteria: 需要新增 runtime permission。
- files / areas likely touched: `ego_desktop_lab/agency_kernel.py`、tests。
- acceptance: kernel output 和 operator report 使用同一 option contract。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_behavior_options_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 option registry 和 tests。
- state: local_pass
- result: kernel now exposes selected behavior only through registered options, while keeping selected intention as policy trace and localizing filtered selections through `selection_restriction`.

### Milestone 3.1: Canonical Event / Plan Contract

- type: implementation
- question: Stage 4 relational companion work 是否会绕过 kernel 直接把自然语言、关系状态或表达策略写进行为选择。
- current framing: 先固定 lab-only `AgencyEvent -> PerceptionFrame -> BehaviorPlan` contract；它是输入/计划审计面，不是第二套 policy、parser 或 gate。
- hypotheses: chat-corpus probes can deterministically produce a `PerceptionFrame`, selected registered behavior can be wrapped into a thin no-action `BehaviorPlan`, and unregistered selections cannot produce plan steps.
- scope: `ego_desktop_lab/agency_contracts.py`, agency kernel result surface, DecisionView read-only formatting, Stage 2.1 chat-corpus parser output, tests.
- experiments planned: stable event/perception derivation, negated-feedback control, selected behavior plan wrapping, unregistered/mismatched plan refusal, DecisionView sections.
- kill criteria: implementing this requires LLM parsing, relation-state mutation, policy-score changes, gate rewrites, runtime bridge, or OpenEmotion writeback.
- files / areas touched: lab contracts, kernel result contract, DecisionView, shell chat-corpus report, Stage 3 tests.
- acceptance: same chat corpus yields stable `AgencyEvent -> PerceptionFrame`; negated repair wording does not trigger negative continue feedback; selected registered option wraps into `BehaviorPlan`; unregistered/mismatched option yields no plan steps; DecisionView displays event/perception/plan/gate/no-action without recomputing decisions.
- validation:
  - `python3 -m py_compile ego_desktop_lab/agency_contracts.py ego_desktop_lab/agency_kernel.py ego_desktop_lab/agency_decision_view.py ego_desktop_lab/shell.py ego_desktop_lab/tests/test_canonical_event_plan_contract_v7_31.py`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_canonical_event_plan_contract_v7_31.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: remove `agency_contracts.py`, contract fields from kernel/DecisionView/shell, and Stage 3.1 tests to return to Stage 3 M2 behavior.
- state: local_pass
- result: canonical event/perception/plan surfaces are now deterministic, read-only in DecisionView, and keep all actions proposal-only with `no_action_executed=true`.

## Progress

- current_status: stage_3_1_local_pass
- current_milestone: Canonical Event / Plan Contract
- milestone_state: local_pass
- candidate_vs_proof: bounded_lab_proof

## Decision log

- 2026-05-14: Stage 3 locked behind experience memory proof。
- 2026-05-15: Stage 2.1 chat-corpus operator acceptance passed; Stage 3 activated for the `Behavior Option Registry Contract` milestone only.
- 2026-05-15: Stage 3.1 inserted before Stage 4 to prevent relational/semantic surfaces from bypassing canonical event/perception/plan contracts.

## Surprises / discoveries

- Stage 2 operator acceptance was enough to unlock Stage 3; further parser/report polish would be a Zeno trap unless the gate regresses.
- The existing DecisionView already carried `debug_refs.recomputed_decision=false`, but formatted output did not show it; Milestone 1 exposed it as an observation-only report improvement.
- Adversarial testing found that affordance-only registration could attach a misleading contract to a malformed action such as `continue_goal + file_delete`; `allowed_actions` now filters this before registration.
- Milestone 2 made the raw policy candidate vs registered behavior relationship explicit: `candidate_options` stay as trace, `behavior_options` are registered/filtered, and `selection_restriction` explains any mismatch.
- Reviewer/operator acceptance found one readability gap: selected intention was only indirectly visible through selection restriction, so `AgencyDecisionView` now renders `Selected Intention` and full selected behavior option JSON directly.
- Stage 3.1 found a Stage 2.1 parser risk: keyword-only feedback could misread negated repair wording. The parser now derives feedback class from `PerceptionFrame`, and negated repair/goal-split phrases no longer create negative continue experience.

## Outcomes / retrospective

- 本轮已证明：registered option contract can be built deterministically from existing intentions and predictions, unregistered affordances and action-affordance mismatches cannot become selected behavior options, kernel-selected behavior is restricted to registered options, gate status remains derived from `GATE_ACTION_STATUS`, canonical option dicts remain JSON-stable through DecisionView/root-cause trace, an operator can inspect selected intention, selected behavior, selection restriction, gate, no-action status, and claim ceiling from one read-only report, and Stage 3.1 now fixes deterministic `AgencyEvent / PerceptionFrame / BehaviorPlan` surfaces before relational companion work begins.
- 还没证明：LLM planner integration, tool autonomy, scheduler autonomy, runtime efficacy, live user benefit, consciousness, or alive status.
- 本轮排除了什么：Stage 3 does not start with LLM planner, tool execution, scheduler, runtime bridge, or permission expansion.
- 下一步最小闭环动作：decide whether to plan Stage 4 (`Relational Companion Layer`) as a separate task packet against the Stage 3.1 contracts. Do not implement Stage 4 from this Stage 3 acceptance note.
