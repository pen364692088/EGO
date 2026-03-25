# MVP11 Audit Report

> Phase B: MVP11 基础验证
> 审计时间: 2026-03-13

---

## 验证范围

MVP11 重点覆盖：
- Cycle C0→C4 链路
- 两层 deterministic replay
- Trace-driven replay
- Hard Gate
- E2E harness
- Testbot Tape/Replay hash
- Shadow→Enforced 治理链

---

## 验证结果汇总

| 项目 | 状态 | 证据 |
|------|------|------|
| 测试通过 | ✅ PASS | 676 passed |
| E2E 执行 | ✅ PASS | pass=true, ticks=200 |
| Replay 一致性 | ✅ PASS | hash_match_rate=1.0, 120/120 matched |
| Hard Gate | ✅ PASS | ALL HARD GATES PASSED |
| Testbot Scenarios | ✅ PASS | 3 scenarios, 14 unique signatures |
| Effect Gate | ✅ PASS | P1-P4 全部通过 |

**最终裁决**: **PASS_STRONG**

---

## 详细证据

### 1. 测试验证

```
tests/mvp11/: 676 passed, 2 warnings in 0.82s
```

测试覆盖：
- `test_replay_determinism.py` - Replay 确定性
- `test_governor_blocks_high_impact.py` - 治理器拦截
- `test_intervention_*.py` - 干预机制
- `test_homeostasis_*.py` - 稳态更新
- `test_cycle_*.py` - Cycle 相关
- `test_concentration_metrics.py` - 浓度指标

### 2. E2E 执行

**命令**:
```bash
python scripts/mvp11_e2e.py --profile ci --eval-mode quick
```

**结果**:
```json
{
  "pass": true,
  "git_sha": "c02ecffe1eb79910e43a0a6d7455054ac9944a01",
  "seed": 42,
  "ticks": 200,
  "science_run_id": "mvp11_1773432935_dd5861d7"
}
```

**关键指标**:
| 指标 | 值 |
|------|-----|
| events | 120 |
| focus_switch_rate | 0.97479 |
| replan_rate | 0.15 |
| governor_block_rate | 0.016667 |
| homeostasis_drift_mean | 0.038239 |

### 3. Replay 一致性

**命令**:
```bash
python scripts/eval_mvp11.py --mode replay --run-id mvp11_1773432935_dd5861d7
```

**结果**:
```json
{
  "mode": "replay",
  "pass": true,
  "replay": {
    "original_events": 120,
    "replay_events": 120,
    "matched": 120,
    "compared": 120,
    "hash_match_rate": 1.0,
    "mismatches": []
  }
}
```

**结论**: ✅ 严格一致，无任何不匹配

### 4. Hard Gate 评估

**命令**:
```bash
python scripts/mvp11_hard_gate_eval.py --shadow-soft-fail
```

**结果**:
```
============================================================
✅ ALL HARD GATES PASSED
============================================================

Testbot E2E Gates (Shadow Mode):
  ✅ Testbot Overall: PASS
     Scenarios:    3 total, 0 failed
     Unique Sigs:  14
     Phi Top1:     0.281

  ✅ tape_hash_match: PASS
  ✅ phi_top1_share: PASS (0.280952 < 0.6)
  ✅ unique_signatures: PASS (14 > 5)
```

### 5. Testbot Scenarios

**命令**:
```bash
python scripts/run_testbot_scenarios.py --subset pr --format json
```

**结果**:
```json
{
  "concentration": {
    "avg_top1_share": 0.280952,
    "avg_hhi": 0.280952,
    "total_unique_signatures": 14
  }
}
```

**解读**:
- 低 concentration = 行为多样性高
- phi_top1_share=0.28 < 0.6 阈值 ✅
- unique_signatures=14 > 5 阈值 ✅

### 6. Effect Gate

**结果**:
```json
{
  "passed": true,
  "epsilon": 0.005,
  "per_prediction": {
    "P1": {"abs_max_delta": 0.87, "passed": true},
    "P2": {"abs_max_delta": 0.109842, "passed": true},
    "P3": {"abs_max_delta": 0.87, "passed": true},
    "P4": {"abs_max_delta": 0.975, "passed": true}
  }
}
```

### 7. Cycle Metrics

**结果**:
```json
{
  "cycle_metrics": {
    "events": 120,
    "dot_ratio": 0.458333,
    "cycle_persistence_score": 0.541667,
    "return_time_mean": 27.15,
    "order_invariance_score": 0.195569,
    "unique_nodes": 80,
    "unique_edges": 117,
    "sanity": {
      "invariant_ok": true,
      "status": "OK"
    }
  }
}
```

---

## 因果链验证

### 主链接线

```python
# emotiond/core.py
from emotiond.governor_v2 import ...
from emotiond.science.cycle import ...
from emotiond.executor_mvp11 import ...
```

**确认**: ✅ 所有核心模块已接入主链

### Replay → Gate 链路

1. 事件输入 → `run.jsonl` 记录
2. `replay_mvp11.py` 读取并重放
3. hash 比对验证一致性
4. `hard_gate_eval.py` 消费 trend/replay/concentration 数据
5. 输出最终判断

**确认**: ✅ 完整链路可审计

---

## 主链真实性

| 检查项 | 状态 | 证据 |
|--------|------|------|
| 模块导入 | ✅ | core.py 显式导入 |
| 运行时调用 | ✅ | E2E 执行证明 |
| 因果作用 | ✅ | intervention 实验通过 |
| 可审计 | ✅ | run.jsonl, tapes, cycle_report 存在 |

---

## 发现的问题

### 1. 导入冲突 (已修复)

**问题**: `emotiond/drives.py` (文件) 与 `emotiond/drives/` (目录) 命名冲突，导致 `Drives` 类无法导入。

**修复**: 使用 `importlib` 直接加载文件。

**文件**:
- `emotiond/science/interventions.py`
- `emotiond/valence_policy.py`

**影响**: 阻塞测试运行，已修复。

---

## 结论

### PASS_STRONG 条件满足

1. ✅ 至少一条完整链路：事件输入 → run.jsonl → replay → gate → 结论
2. ✅ hash/replay 无关键不一致
3. ✅ gate 能根据真实 artifacts 给出判断，而非空跑
4. ✅ 测试覆盖充分
5. ✅ 因果干预有效

### 证据链完整性

| 证据类型 | 位置 |
|----------|------|
| 运行日志 | `artifacts/mvp11/mvp11_1773432935_dd5861d7.jsonl` |
| Cycle 报告 | `artifacts/mvp11/mvp11_1773432935_dd5861d7/cycle_report.json` |
| Replay 结果 | `artifacts/mvp11/eval_replay_mvp11_1773432935_dd5861d7.json` |
| Testbot Tapes | `artifacts/testbot/tapes/*.jsonl` |
| Hard Gate 报告 | (运行时生成) |

---

## 裁决

**MVP11**: **PASS_STRONG**

- 机制存在: ✅
- 可运行: ✅
- 起作用: ✅
- 可证明起作用: ✅

---

*审计完成时间: 2026-03-13*
