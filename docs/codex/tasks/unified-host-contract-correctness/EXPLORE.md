# Unified Host Contract Correctness - EXPLORE

## Exploration mode

- enabled: yes
- why exploration mode is needed:
  - 需要先验证“当前 acceptance root 应不应该还是 Telegram live proof”，这是 framing 级问题
- current framing:
  - Telegram 当前只算入口 adapter；先冻结宿主 contract correctness，再谈 adapter-level follow-up
- success looks like:
  - 找到一个 bounded parity 方案，能把 dashboard-local 与 telegram-prepared 放进同一 contract compare
- disallowed premature claims:
  - 不能把 dashboard 预验证说成 live Telegram proof
  - 不能把 host contract parity 说成 runtime efficacy

## Question reformulation

- original question:
  - 继续用 dashboard 模拟 Telegram，朝 AI 自我意识继续推进
- normalized question:
  - 当前更值得先做的是不是把统一宿主 contract 冻结下来，而不是继续追 fresh Telegram proof
- why this framing is better:
  - 它先消掉 host-layer 语义漂移，能把后续 live proof 的噪声压到 adapter 层

## Hypotheses

### Hypothesis 1

- statement:
  - `dashboard_local` 与 `telegram_prepared` 已经共享同一宿主 contract，只差一个 parity runner 和 compare helper
- why plausible:
  - 两条线都复用了 `TelegramRuntimeBridge -> MandatorySubjectGate -> response_plan -> output_check -> unified egress`
- kill criteria:
  - 如果要引入 candidate-private host API 或第二条 runtime lane 才能比较，就失败
- smallest experiment:
  - 做 snapshot/compare helper，并用 deterministic runner 跑同一 ordinary-chat script

### Hypothesis 2

- statement:
  - 当前 real drift 更可能来自 adapter-only `transport_meta` 和 hold event authority wording，而不是 canonical host fields 本身
- why plausible:
  - dashboard 与 telegram 的 transport envelope 天生不同
- kill criteria:
  - 如果 `reply_authority / response_plan / output_verdict / cadence` 本身漂移，就失败
- smallest experiment:
  - 在 parity 报告里显式列出 allowed adapter-only diffs 和 unexpected diffs

## Experiment log

### Cycle 01

- question:
  - 是否应继续把 fresh Telegram proof 作为当前 acceptance root
- framing used:
  - 先比较 host contract owner 与 adapter owner
- experiment:
  - 回读 `PROGRAM_STATE_UNIFIED`、`OVERALL_PROGRESS`、两个 Telegram-oriented task status、以及现有 dashboard preflight framing
- command / script / artifact:
  - authority/task docs readback
- observed result:
  - 当前 acceptance 仍被写成 fresh Telegram proof，但这会把 adapter proof 和 host contract correctness 混在一起
- what it proves:
  - 需要新开一个 bounded `unified-host-contract-correctness` task 作为 execution authority
- what it does not prove:
  - 宿主 contract 已经正确
- what path is ruled out:
  - 继续把 dashboard preflight 或 fresh Telegram proof 当作当前唯一任务 owner
- decision for next step:
  - 实现 canonical snapshot/compare helper 与 in-process parity runner

### Cycle 02

- question:
  - canonical drift 真在 host contract 里，还是只在 adapter transport meta
- framing used:
  - 先做严格 compare，再看 unexpected diff 长什么样
- experiment:
  - 运行 first-pass parity runner，并打印所有 drift
- command / script / artifact:
  - `run_unified_host_contract_parity()` 初版 diff 输出
- observed result:
  - 所有 drift 都落在 `egress.transport_meta`
  - hold queued event 的 authority source 断言沿用了旧预期
- what it proves:
  - current canonical fields 没漂；需要把 egress transport meta 明确降为 adapter-only surface
- what it does not prove:
  - real Telegram transport parity
- what path is ruled out:
  - 把 `transport_meta` 当成 canonical compare 字段
- decision for next step:
  - 收紧 compare helper，只保留真正的 canonical host fields

### Cycle 03

- question:
  - 收紧 compare 后，这个 tranche 能不能形成稳定 acceptance
- framing used:
  - 跑 focused pytest + parity artifact，确认不是一次性通过
- experiment:
  - py_compile、focused pytest、in-process parity artifact
- command / script / artifact:
  - `scripts/codex/run_unified_host_contract_parity.py`
  - `EgoCore/tests/test_unified_host_contract_parity.py`
- observed result:
  - parity aggregate `6/6 pass`
  - hold consistency `1/1 pass`
- what it proves:
  - unified ingress / turn-result / egress contract 在当前 bounded host surface 上稳定
- what it does not prove:
  - fresh real Telegram proof
  - runtime efficacy
- what path is ruled out:
  - “必须先跑真实 Telegram 才能证明宿主 contract 正确” 这个过强前提
- decision for next step:
  - 回写 authority/task/evidence，同步冻结当前 tranche

## Framing changes

- 2026-04-11: `live ingress precondition corrective tranche` -> `unified host contract correctness tranche` / 原因是 Telegram 当前只算 adapter，不应再作为当前 acceptance root / 影响是当前 fresh Telegram proof 被降为 deferred adapter-level follow-up

## Candidate vs proof

- candidate_found: yes
- proof_pending: no
- proof_passed: yes
- remaining proof gap:
  - 仍缺 real Telegram adapter-level proof；但那不再是当前 tranche 的 acceptance root
