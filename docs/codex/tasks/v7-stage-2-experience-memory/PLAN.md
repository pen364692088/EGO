# v7 Stage 2 - Experience Memory - PLAN

## Task summary

实现 lab-only experience memory，把 outcome/root-cause 转成可影响 future ranking 的经验卡。

## Execution mode

- mode: implementation
- why this mode: 需要新增小型 contract 和定向测试。
- proof required after discovery: 相似场景行为改变、无关场景不变、冲突降权。

## Milestones

### Milestone 1: ExperienceCard Contract

- type: implementation
- question: 什么经验可被复用，什么经验应降权。
- current framing: 经验是可反证的策略偏置，不是永久事实。
- hypotheses: rule-based applicability 足够第一版。
- scope: `ego_desktop_lab/experience_memory.py`。
- experiments planned: positive/negative/conflict/unrelated 四类经验。
- kill criteria: 需要 embedding 或 LLM 才能通过第一版验收。
- files / areas likely touched: `ego_desktop_lab/experience_memory.py`、tests。
- acceptance: ExperienceCard 可序列化、可 replay、可降权。
- validation:
  - `python3 -m py_compile ego_desktop_lab/experience_memory.py`
- rollback note: 删除新增 module/tests。

### Milestone 2: Kernel Bias Integration

- type: implementation
- question: experience bias 是否能影响 option ranking 且不绕过 gate。
- current framing: memory 影响 tendency，不影响 permission。
- hypotheses: 接入 pressure/strategy bias 即可。
- scope: lab kernel input extension。
- experiments planned: 相似任务 ranking 改变，无关任务不变。
- kill criteria: 需要改 EgoCore/OpenEmotion 才能证明。
- files / areas likely touched: `ego_desktop_lab/agency_kernel.py`、tests。
- acceptance: deterministic replay shows behavior tendency change.
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_experience_memory_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 kernel bias input 和 experience module。

## Progress

- current_status: deterministic_pass
- current_milestone: ExperienceCard Contract + Kernel Bias Integration
- milestone_state: deterministic_pass
- candidate_vs_proof: local_deterministic_proof

## Decision log

- 2026-05-14: Stage 2 locked behind deterministic kernel proof。
- 2026-05-14: Stage 1 local proof was accepted by user/operator check; Stage 2 activated for lab-only implementation.
- 2026-05-14: Experience memory was implemented as contextual bias, not a second StrategyMemory authority.
- 2026-05-14: Added operator-supplied custom JSON case runner so Stage 2 can be checked outside built-in fixtures.
- 2026-05-14: Added operator usability closeout scope: custom JSON BOM compatibility and direct behavior-change summary in reports.
- 2026-05-14: Added Stage 2.1 chat-corpus operator probe so Markdown transcript cases can be deterministically converted into replayable experience-memory probes.

## Surprises / discoveries

- ExperienceCard can use deterministic context signatures for the first slice; no embedding or LLM similarity is required.
- Conflict handling is safest as `needs_review` with no bias rather than averaging contradictory lessons into action tendency.
- Fixed fixtures are insufficient for human confidence; the shell now supports a temporary operator-provided JSON case.
- Raw ranking JSON is insufficient for manual checks; report must spell out before/after behavior, rank, priority delta, gate, and no-action status.
- Handwritten JSON is still too high-friction for human testing; chat-corpus probes preserve replayability while letting the operator provide normal dialogue snippets.

## Outcomes / retrospective

- 本轮已证明：lab-only ExperienceCard can change future ranking in a similar context, leave unrelated contexts unchanged, mark conflicts as `needs_review`, keep gate/no-action invariants, run operator-supplied JSON and Markdown chat-corpus cases, and expose the before/after behavior change in an operator-readable report.
- 还没证明：runtime persistence, long-term user memory, OpenEmotion memory mutation, live benefit, or computer skill learning.
- 本轮排除了什么：Stage 2 does not require embedding similarity, LLM memory retrieval, runtime persistence, or OpenEmotion state writes.
- 下一步最小闭环动作：run the Stage 2.1 chat-corpus operator probe manually before deciding whether Stage 3 behavior option framework can unlock.
