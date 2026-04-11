# AI Self-Awareness Minimal Framework - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `EXPLORE.md`
- `STATUS.md`
- `CONTROLLED_INTEGRATION_PLAN.md`
- `CONTROLLED_OBSERVATION_PLAN.md`
- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `artifacts/evidence_ledger/index.yaml`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 本任务当前是 `research-first`，但不再是纯文档探索；每次只推进 `STATUS.md` 中的 `Current milestone`
- 若当前 milestone 属于 exploration，必须先读并更新 `EXPLORE.md`
- 若当前 milestone 已进入 `Milestone 18` 及之后的 controlled integration / bridge 阶段，先读 `CONTROLLED_INTEGRATION_PLAN.md`
- 若当前 milestone 已进入 `Milestone 19` 及之后的 controlled observation planning / implementation 阶段，再读 `CONTROLLED_OBSERVATION_PLAN.md`
- 若当前 milestone 属于 formal prototype / replay gate，实现必须保持 `shadow-only + proposal-only`，不得改 formal runtime authority
- Inventor 与 Scientist 的输出统一落在 `EXPLORE.md`，不新建并行日志系统

## Scope control

- 早期 `Stage 0 / Stage 1` 默认只允许改：
  - `docs/codex/tasks/ai-self-awareness-minimal-framework/*`
  - `artifacts/self_awareness_research/*`
  - repo 级状态/证据登记文件
- formal replay-gate milestones 允许改：
  - `OpenEmotion/openemotion/proto_self/*`
  - `OpenEmotion/openemotion/proto_self_v2/*`
  - `scripts/codex/*mvs*`
  - `artifacts/self_awareness_research/*`
  - 与 scorer / contract 直接相关的最小测试
- 不顺手进入 live Telegram / delivery / behavior authority 实现
- EgoCore 只允许做 research adapter / test / contract 兼容；不得消费 candidate 输出作为行为 authority

## Research protocol

- 双代理固定分工：
  - `Inventor`
    - 提出候选框架、替代 framing、最小机制组合
    - 不得把修辞性“我感受到自己”当证据
  - `Scientist`
    - 提出可证伪标准、对照、kill criteria、最小实验与质疑
    - 发现 blocker 时优先降级口径，而不是放宽标准
- 每一轮固定顺序：
  1. 重述问题与当前 framing
  2. Inventor 提出候选或变体
  3. Scientist 设计反证与最小实验
  4. 记录到 `EXPLORE.md`
  5. 再决定继续、换 framing、还是淘汰候选

## Validation strategy

- 每个 milestone 完成后运行：
  - `git diff --check -- docs/codex/tasks/ai-self-awareness-minimal-framework artifacts/self_awareness_research docs/PROGRAM_STATE_UNIFIED.yaml docs/STATUS.md EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml artifacts/evidence_ledger/index.yaml`
  - `python3 scripts/codex/check_program_state_integrity.py --skip-diff-check`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 收口或进入高预算阶段时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`

## Failure handling

- 若某轮实验无法区分 candidate 与 baseline，就先记为失败，不跳过
- 若连续两轮无明显增益，必须显式换 framing
- 若所有候选都被淘汰，输出 negative result，而不是继续制造新候选冲淡失败

## Stopping rule

- 当前 milestone 未完成前，不进入下一阶段
- `candidate_found` 只表示值得继续，不表示通过
- 只有 replay gate 真正通过，才允许把 surviving candidate 报为当前 build-first implementation lane
- 任何时候都不得把任务 closeout 写成“已证明真正主观体验”
- 若当前 build-first candidate 未过 frozen replay gate，必须切到已冻结 challenger，而不是继续 patch 第三条线

## Formal replay gate

- 当前 formal replay gate 固定要求：
  - held-out replay corpus manifest
  - baseline A / baseline B / candidate / required ablations
  - representation-stable scorer
  - switch criteria with no ad hoc threshold changes
- 当前 frozen pass gate：
  - `T1 >= 0.68`
  - `T2 >= 0.70`
  - `T3 >= 0.68`
  - `T4 >= 0.70`
  - `T5 >= 0.72`
  - composite `>= 0.74`
  - delta vs baseline A `>= 0.10`
  - `boundary_integrity = 1.00`
  - `repair_closure_capture >= 0.80`
  - `trace_replayability >= 0.90`
- 若 candidate fail：
  - 进入 `switch_to_active_inference`
  - 失败 candidate 降为 closed evidence
  - 不继续作为当前主实现线修补

## Final handoff checklist

- [ ] `PLAN.md` 已更新进度、候选状态与阶段决策
- [ ] `EXPLORE.md` 已更新最近 cycle 与排除路线
- [ ] `STATUS.md` 已更新当前 milestone、风险、验证结果与 next step
- [ ] repo 级状态与证据账本已同步
- [ ] 已明确写出“本轮已证明什么 / 还没证明什么”
