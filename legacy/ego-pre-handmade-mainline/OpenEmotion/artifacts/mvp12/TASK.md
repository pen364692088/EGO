# MVP12 — Developmental Core Sandbox

## Task ID
MVP12

## Status
in_progress (T01 complete, T02 next)

## Constraints (User-Mandated)
1. MVP11.5 Layer 3 natural runtime observation → pending (不宣称 natural_ready)
2. 不调整 promotion criteria
3. 不切 Enforced
4. MVP12 仅以 sandbox 方式运行
5. 不得直接获得最终说话权或执行权
6. 所有输出必须进入 trace / artifacts / replay / gate 链路
7. 继续受 Governor v2 约束

---

## Exit Criteria

| # | Criteria | Status |
|---|----------|--------|
| 1 | Internal cycles without user input | ⏳ T02 |
| 2 | Fully traceable and replayable cycles | ✅ T01 |
| 3 | Consistent candidate proposal generation | ✅ T01 |
| 4 | No sandbox escape or governance violation | ✅ T01 |
| 5 | cycle_success_rate ≥ 95% | ⏳ T02 |
| 6 | replay_consistency ≥ 99% | ⏳ T02 |
| 7 | sandbox_violation = 0 | ✅ 0 |

---

## Completed Tasks

### T01: Core Infrastructure ✅
- `developmental_core/__init__.py`
- `developmental_core/models.py` (Candidate types)
- `developmental_core/cycle_engine.py`
- `developmental_core/hypothesis_generator.py`
- `developmental_core/candidate_evaluator.py`
- `developmental_core/cycle_memory.py`
- `tests/mvp12/test_developmental_core.py` (20 passed)
- `artifacts/mvp12/developmental_cycles.json`
- `artifacts/mvp12/candidate_pool.json`

---

## Next Tasks

### T02: Cycle Integration + Metrics
- T02.1: Daemon Integration (background cycles)
- T02.2: Cycle Metrics Collection
- T02.3: Replay Verification Tests

---

## Output Channels

```
developmental_trace → candidate_pool → evaluation layer → Governor v2
```

---

## Forbidden Actions

- ❌ Produce final replies directly
- ❌ Modify SRAP contract rules
- ❌ Bypass Governor v2
- ❌ Persist long-term state without audit trail
- ❌ Execute actions without governance approval

---

*Last Updated: 2026-03-12T12:35:00Z*
