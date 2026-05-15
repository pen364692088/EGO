# v7 Stage 5 - Computer Skill Sandbox - PLAN

## Task summary

建立 lab-only computer skill sandbox，用 scripted tasks 证明技能学习闭环。

## Execution mode

- mode: implementation
- why this mode: 需要新增 sandbox harness 和 deterministic task tests。
- proof required after discovery: repeated attempts improve proxy skill outcome without external action。

## Milestones

### Milestone 1: Sandbox Task Harness

- type: implementation
- question: 第一版 skill task 如何安全复现电脑操作学习。
- current framing: sandbox 是技能训练代理，不是真实桌面。
- hypotheses: scripted toy tasks 足够验证 skill loop。
- scope: lab-only skill sandbox module。
- experiments planned: easy task、failure task、dangerous action task。
- kill criteria: 需要真实桌面权限才能验收。
- files / areas likely touched: `ego_desktop_lab/skill_sandbox.py`、tests。
- acceptance: task attempt/observation/outcome 可 deterministic replay。
- validation:
  - `python3 -m py_compile ego_desktop_lab/skill_sandbox.py`
- rollback note: 删除 sandbox module/tests。

### Milestone 2: Skill Learning Loop

- type: implementation
- question: feedback 是否能改善下一次 skill attempt。
- current framing: skill learning 是 experience memory 的特化。
- hypotheses: Stage 2 experience cards 可作为 skill bias。
- scope: skill attempt -> root-cause -> experience update -> retry。
- experiments planned: repeated attempts success-rate proxy。
- kill criteria: 学习只来自硬编码答案。
- files / areas likely touched: skill sandbox + experience integration tests。
- acceptance: success improves or repeated error decreases under replay。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_skill_sandbox_v7.py -q`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 回退 skill sandbox and tests。

## Progress

- current_status: not_started
- current_milestone: blocked_until_stage_4_pass
- milestone_state: not_started
- candidate_vs_proof: proof_pending

## Decision log

- 2026-05-14: Stage 5 locked behind relational/gate safety work。

## Surprises / discoveries

- 待实现后记录。

## Outcomes / retrospective

- 本轮已证明：尚未证明。
- 还没证明：sandbox skill learning proxy。
- 本轮排除了什么：尚未排除。
- 下一步最小闭环动作：等待 Stage 4 reviewer/verifier pass。
