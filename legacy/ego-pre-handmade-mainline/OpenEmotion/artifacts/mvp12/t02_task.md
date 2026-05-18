# T02: Cycle Integration + Metrics

## Task ID
T02

## Phase
MVP12 — Developmental Core Sandbox

## Status
in_progress

## Objective
将 developmental core 集成到 emotiond daemon，收集周期指标。

---

## Subtasks

### T02.1: Daemon Integration
- 修改 `emotiond/dmn_tick.py` 添加 developmental cycle tick
- Wire CycleEngine into background process
- 尊重 idle/timeout 触发器
- 输出: 修改后的 dmn_tick.py

### T02.2: Cycle Metrics Collection
- 实现 sandbox_metrics.json 指标收集
- 指标:
  - cycle_success_rate
  - replay_consistency
  - candidate_pool_size
  - avg_candidates_per_cycle
- 输出: `artifacts/mvp12/sandbox_metrics.json`

### T02.3: Replay Verification Tests
- 测试相同 seed 的确定性重放
- 验证 trace_hash 稳定性
- 添加到 tests/mvp12/test_replay.py
- 输出: replay_consistency 指标

---

## Constraints
- No final reply generation
- No direct action execution
- All outputs through Governor v2

---

## Success Criteria
- [ ] Developmental cycles run as background process
- [ ] Metrics collected and persisted
- [ ] Replay verification tests pass
- [ ] sandbox_violation remains 0

---

## Allowed Write Targets
- `emotiond/developmental_core/`
- `emotiond/dmn_tick.py`
- `artifacts/mvp12/`
- `tests/mvp12/`
