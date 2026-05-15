# v7 Stage 0 - Operator Observability - PLAN

## Task summary

实现 lab-only operator observability cut，让用户能检查当前 v7 agent 的决策、失败归因和下一步最小验证。

## Execution mode

- mode: implementation
- why this mode: contract 和输入面已存在，当前任务是把它组织成可运行报告。
- proof required after discovery: 单命令 report + root-cause tests + scoped diff check。

## Milestones

### Milestone 1: Report Contract

- type: implementation
- question: operator report 是否能只读现有 result/view 并解释当前决策。
- current framing: 观测优先于继续扩展主体机制。
- hypotheses: `AgencyDecisionView + RootCauseTrace` 足够支撑第一版 report。
- scope: `ego_desktop_lab` report/shell surface 与本任务文档。
- experiments planned: 构造成功和失败样例，验证 report 字段完整。
- kill criteria: report 需要重新运行 policy/gate 才能解释结果。
- files / areas likely touched: `ego_desktop_lab/shell.py` 或新增 lab-only report helper。
- acceptance: report 包含 boundary / viability / prediction / ranking / gate / plasticity / root cause。
- validation:
  - `python3 -m py_compile ego_desktop_lab/*.py`
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests/test_root_cause_observability_v7_1.py -q`
- rollback note: 删除新增 report helper 与对应测试即可回退。

### Milestone 2: Operator Command

- type: implementation
- question: 用户是否能用一个命令生成报告。
- current framing: 可测试性必须成为每个后续 stage 的入口。
- hypotheses: 可复用现有 shell/report builder。
- scope: lab-only CLI/report builder，不接 runtime。
- experiments planned: 运行单命令生成报告到 `tmp_path` 或测试内存。
- kill criteria: 命令写入 repo temp/log/runtime JSONL。
- files / areas likely touched: `ego_desktop_lab/shell.py`、`ego_desktop_lab/tests/`。
- acceptance: 命令可复现，报告不包含强 claim。
- validation:
  - `TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m pytest ego_desktop_lab/tests -q`
- rollback note: 删除命令入口，保留 root-cause contract。

## Progress

- current_status: local_pass
- current_milestone: Reviewer Gate
- milestone_state: local_pass
- candidate_vs_proof: local_proof_only

## Decision log

- 2026-05-14: Stage 0 作为唯一 active stage；原因是没有观测面会导致后续 stage 黑盒化。

## Surprises / discoveries

- `STATUS.md` 必须使用全局允许状态枚举；本轮 reviewer 将
  `local_verified` 收敛为 `local_pass`。

## Outcomes / retrospective

- 本轮已证明：Stage 0 可以生成 lab-only operator report，覆盖 boundary /
  viability / prediction / ranking / gate / plasticity / root cause，并能通过
  单命令写入指定 path；human-usability closeout 后，报告也直接展示
  before/after selected goal、selected-intention change、rank/priority delta、
  prediction error delta 和具体 `continue_failure` replay probe。
- 还没证明：runtime efficacy、live user benefit、真实 Telegram 路径、Stage 1+
  机制进展。
- 本轮排除了什么：报告层重新计算 selected option / policy / gate。
- 下一步最小闭环动作：reviewer 判定是否解锁 Stage 1；当前不自动推进。
