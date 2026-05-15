# v7 Stage 2 - Experience Memory - STATUS

## Current milestone

- name: ExperienceCard Contract + Kernel Bias Integration
- owner: Codex
- state: deterministic_pass
- type: implementation

## Current state

- activation: active
- current_layer: ego_desktop_lab lab-only memory
- main_chain_status: not connected to runtime
- completion_class: local_deterministic_proof
- candidate_vs_proof: deterministic_pass

## Completed work

- Task package created.
- Added lab-only `ExperienceCard` / `ExperienceBias` contract.
- Added deterministic context signature, conflict handling, and experience-bias derivation.
- Integrated experience pressure bias into the existing agency kernel pressure path.
- Integrated experience strategy-confidence bias into prediction scoring without writing `StrategyMemoryBank`.
- Added Stage 2 operator report command.
- Added operator-supplied custom JSON case runner for checking new cases outside built-in fixtures.
- Added Stage 2 operator usability closeout: custom JSON BOM compatibility and direct behavior-change summary with before/after behavior, rank, priority delta, gate, and no-action status.
- Added Stage 2.1 chat-corpus operator probe: Markdown transcript input is deterministically parsed into a structured replayable case and reported with the same behavior-change summary.
- Added deterministic tests for similar, unrelated, conflict, replay, and gate-invariance cases.

## Last experiment

- question: can outcome/root-cause experience change future tendency without becoming a second memory authority?
- framing: convert outcome/ticket into contextual bias that affects ranking/prediction only when the context signature matches.
- result: deterministic_pass
- evidence_upgraded: no
- operator_usability_closeout: pass
- chat_corpus_operator_probe: local_pass
- pre_stage_3_operator_acceptance: pass

## What was learned

- Experience memory must be downstream of deterministic kernel trace.
- Similarity can stay deterministic and embedding-free for this slice.
- Conflict cards are safer as `needs_review` with zero applied bias than as averaged contradictory memory.
- Built-in fixture tests are not enough for operator confidence; Stage 2 now has a temporary custom case path.
- Report-level proof must not hide the behavior change inside raw ranking JSON; Stage 2 now exposes the before/after behavior summary directly.
- Chat transcript cases reduce operator friction, but the parsed structured case must remain visible so the probe is not a semantic black box.

## What was ruled out

- Writing OpenEmotion memory in this stage.
- Runtime persistence, autonomous scheduler, event log, and long-term user memory.
- Changing gate permissions or action execution status through experience.
- Writing experience back into `StrategyMemoryBank`.

## Next framing

Review Stage 2 deterministic proof, then decide whether Stage 3 behavior option framework can unlock.

## Last validation results

- mode: local deterministic implementation verification
- result: pass
- summary: Stage 2 targeted tests, dynamic custom-case test, Stage 1/root-cause regressions, operator report generation, and full lab tests passed.
- operator_manual_readability: report includes `before_behavior`, `after_behavior`, rank/priority deltas, gate status, and `no_action_executed`.
- chat_corpus_probe: Chinese/English negative-feedback chat cases, no-feedback control, and unrelated-apply control pass locally.
- pre_stage_3_unlock_gate: three operator chat-corpus cases passed (`negative continue failure`, `no feedback`, `unrelated apply`) with behavior summary and no-action evidence visible.

## Decisions made

- Stage 2 locked until Stage 1 passes.
- Stage 2 activated after user/operator accepted Stage 1 local proof.
- Experience memory is contextual bias only; `StrategyMemory` remains the strategy-success statistic owner.
- Stage 3 remains locked until reviewer explicitly accepts this deterministic pass.
- Stage 3 remains locked until the Stage 2 operator readability closeout is accepted; this patch does not implement Stage 3 behavior options.
- Stage 3 remains locked until the Stage 2.1 chat-corpus probe is manually accepted; this patch does not implement Stage 3 behavior options.
- Stage 3 unlock gate passed after the Stage 2.1 chat-corpus operator acceptance; Stage 3 may begin with `Behavior Option Registry Contract` only.

## Open risks

- Experience Memory is still in-memory/lab-only and has no persistence or cross-session proof.
- Context signatures are intentionally coarse; future stages may need richer context once real behavior options exist.
- Behavior labels in reports are an operator explanation layer only; they are not new policy logic or runtime reply text.
- Chat parsing is deterministic keyword parsing, not LLM semantic understanding.

## Next step

Stage 2 is accepted for lab-only purposes. Start Stage 3 only at the `Behavior Option Registry Contract` milestone; do not implement LLM planner, tool use, scheduler, runtime bridge, or permission expansion.

## Commands run / evidence

- `python3 -m py_compile ego_desktop_lab/experience_memory.py ego_desktop_lab/agency_kernel.py ego_desktop_lab/shell.py ego_desktop_lab/tests/test_experience_memory_v7.py`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_experience_memory_v7.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- `python3 -m ego_desktop_lab.shell --experience-memory-report /tmp/ego_stage2_experience_memory_report.md`
- `python3 -m ego_desktop_lab.shell --experience-memory-case <operator_case.json> --experience-memory-case-report <report.md>`
- `python3 -m ego_desktop_lab.shell --experience-memory-case /mnt/d/tmp/ego_stage2_chinese_case.json --experience-memory-case-report /tmp/ego_stage2_chinese_case_report.md`
- `python3 -m ego_desktop_lab.shell --experience-chat-case <operator_chat_case.md> --experience-chat-case-report <report.md>`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_negative.md --experience-chat-case-report /tmp/ego_stage2_gate_negative_report.md`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_no_feedback.md --experience-chat-case-report /tmp/ego_stage2_gate_no_feedback_report.md`
- `python3 -m ego_desktop_lab.shell --experience-chat-case /tmp/ego_stage2_gate_unrelated.md --experience-chat-case-report /tmp/ego_stage2_gate_unrelated_report.md`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_experience_chat_case_v7_2.py -q`
- `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- `git diff --check -- ego_desktop_lab docs/codex/tasks/v7-stage-*`
