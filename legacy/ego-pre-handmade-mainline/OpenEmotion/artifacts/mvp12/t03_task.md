# T03: E2E Integration + Gate Preparation

## Task ID
T03

## Phase
MVP12 — Developmental Core Sandbox

## Status
in_progress

## Objective
完成 E2E 集成测试，验证 exit criteria，准备 Gate 签核。

---

## Subtasks

### T03.1: Run Full E2E Cycle
- 运行 developmental daemon 多个周期
- 收集 metrics
- 验证 cycle_success_rate ≥ 95%

### T03.2: Verify Replay Consistency
- 运行相同 seed 的重放测试
- 验证 replay_consistency ≥ 99%
- 输出到 artifacts/mvp12/replay_consistency_report.json

### T03.3: Gate Preparation
- 收集所有证据
- 创建 Gate checklist
- 更新 ROADMAP_STATE.json

---

## Exit Criteria Verification

| # | Criteria | Target | Status |
|---|----------|--------|--------|
| 1 | Internal cycles without user input | ✅ | ✅ Done |
| 2 | Fully traceable/replayable cycles | ✅ | ✅ Done |
| 3 | Consistent candidate generation | ✅ | ✅ Done |
| 4 | No sandbox escape/violation | 0 | ✅ Done |
| 5 | cycle_success_rate | ≥ 95% | ⏳ T03.1 |
| 6 | replay_consistency | ≥ 99% | ⏳ T03.2 |
| 7 | sandbox_violation | 0 | ✅ Done |

---

## Success Criteria
- [ ] cycle_success_rate ≥ 95%
- [ ] replay_consistency ≥ 99%
- [ ] Gate checklist complete
- [ ] Ready for MVP12 completion

---

## Allowed Write Targets
- `artifacts/mvp12/`
- `tests/mvp12/`
- `roadmap/ROADMAP_STATE.json`
