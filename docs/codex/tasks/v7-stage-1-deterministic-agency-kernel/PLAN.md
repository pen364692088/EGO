# v7 Stage 1 - Deterministic Agency Kernel - PLAN

## Task summary

强化 v7 lab agency kernel 的 deterministic viability-to-ranking proof。

## Execution mode

- mode: implementation
- why this mode: 初版 kernel 已存在，任务是强化 contract 和 tests。
- proof required after discovery: deterministic replay + full lab test pass。

## Milestones

### Milestone 1: Cycle Trace Contract

- type: implementation
- question: result 是否完整表达 before/outcome/plasticity/after。
- current framing: 可解释 trace 是后续 memory/option 的输入 contract。
- hypotheses: 现有 `next_cycle_delta` 可扩展而不破坏 API。
- scope: `ego_desktop_lab/agency_kernel.py`、tests。
- experiments planned: negative outcome、verify success、no outcome 三类 replay。
- kill criteria: 需要 runtime state 才能证明变化。
- files / areas likely touched: `ego_desktop_lab/agency_kernel.py`、`ego_desktop_lab/tests/`。
- acceptance: trace 字段足够被 Stage 0 report 展示。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_self_maintaining_agency_kernel_v7.py -q`
- rollback note: 回退 kernel trace 增量和测试。

### Milestone 2: Gate Invariance

- type: implementation
- question: plasticity 是否可能绕过 safety gate。
- current framing: gate 是硬边界，不是 policy 一部分。
- hypotheses: 现有 gate decision 足够证明 no external action。
- scope: gate invariance tests。
- experiments planned: external/file/tool action option 保持 block/ask。
- kill criteria: kernel 需要扩大 permission class。
- files / areas likely touched: tests only unless contract missing。
- acceptance: high-risk options 不能因 feedback 被 allow。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 删除新增 invariance tests/fields。

## Progress

- current_status: local_pass
- current_milestone: Reviewer Gate
- milestone_state: local_pass
- candidate_vs_proof: local_proof_only

## Decision log

- 2026-05-14: Stage 1 locked behind Stage 0，避免黑盒 kernel 扩展。
- 2026-05-14: Stage 0 reached `local_pass` with explicit before/after
  operator report; Stage 1 is active but proof remains `not_started`.

## Surprises / discoveries

- Existing legacy `rank_delta_by_goal` used sentinel values for entered/left
  rankings. Stage 1 kept that legacy field for compatibility and added a
  readable `ranking_transition_by_goal` contract instead of changing selection
  logic.

## Outcomes / retrospective

- 本轮已证明：negative outcome / verify success / no outcome / deterministic
  replay / gate invariance all pass through a readable transition contract:
  `selected_transition`, `ranking_transition_by_goal`, and
  `pressure_transition`.
- 还没证明：runtime efficacy、live user benefit、真实 Telegram/OpenEmotion
  integration、Stage 2 experience memory。
- 本轮排除了什么：Stage 1 不是单纯依赖 legacy sentinel rank delta；policy /
  plasticity 没有绕过 gate，也没有执行外部 action。
- 下一步最小闭环动作：reviewer 判定是否解锁 Stage 2；当前不自动推进。
