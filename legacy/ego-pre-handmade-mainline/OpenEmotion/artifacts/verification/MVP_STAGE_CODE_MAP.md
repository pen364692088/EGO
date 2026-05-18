# MVP Stage → Code/Script/Test/Artifact Mapping

> Phase A: 仓库结构与阶段映射审计
> 生成时间: 2026-03-13

---

## 映射表总览

| Stage | 核心模块 | 脚本 | 测试 | Artifacts | 主链接线 |
|-------|---------|------|------|-----------|---------|
| MVP11 | cycle, replay, testbot, governor | mvp11_e2e.py, replay_mvp11.py, hard_gate_eval.py | tests/mvp11/ (32 tests) | artifacts/mvp11/ | ✅ 完整 |
| MVP11.5 | response_intent_checker, srap | run_testbot_scenarios.py | tests/testbot/, test_response_intent_checker.py | artifacts/mvp11_5/ | ✅ shadow mode |
| MVP12 | developmental_core/ | e2e_test_mvp12.py, replay_consistency_mvp12.py | tests/mvp12/ (31 tests) | artifacts/mvp12/ | ❌ 未验证 |
| MVP13 | self_model/ | - | tests/mvp13/ (21 tests) | artifacts/mvp13/ | ⚠️ 部分 (legacy) |
| MVP14 | drives/ | - | tests/mvp14/ (12 tests) | artifacts/mvp14/ | ❌ 未接线 |
| MVP15 | reflection_engine/ | - | tests/mvp15/ (9 tests) | artifacts/mvp15/ | ❌ 未接线 |
| MVP16 | developmental/ | mvp16_daily_check.py | tests/mvp16/ (30 tests) | artifacts/mvp16-observation/ | ❌ 未接线 |

---

## MVP11: Cycle Governance / Deterministic Replay / Hard Gate / E2E Harness / Testbot

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/science/cycle.py` | Cycle C0→C4 链路 | ✅ core.py |
| `emotiond/science/cycle_store.py` | Cycle 存储 | ✅ |
| `emotiond/science/cycle_graph.py` | Cycle 图分析 | ✅ |
| `emotiond/science/ledger.py` | 状态账本 | ✅ |
| `emotiond/science/interventions.py` | 干预机制 | ✅ |
| `emotiond/science/concentration.py` | 浓度指标 | ✅ |
| `emotiond/governor_v2.py` | 治理器 v2 | ✅ core.py |
| `emotiond/testbot/harness.py` | Testbot harness | ✅ |
| `emotiond/testbot/tape.py` | Testbot tape | ✅ |
| `emotiond/testbot/assertions.py` | Testbot 断言 | ✅ |
| `emotiond/cycle_prior.py` | Prior guards | ✅ |
| `emotiond/cycle_prior_guards.py` | Prior 守卫 | ✅ |
| `emotiond/executor_mvp11.py` | MVP11 执行器 | ✅ |

### 脚本
| 文件 | 功能 |
|------|------|
| `scripts/mvp11_e2e.py` | E2E 测试入口 |
| `scripts/replay_mvp11.py` | 回放验证 |
| `scripts/cycle_analyze_mvp11.py` | Cycle 分析 |
| `scripts/cycle_graph_mvp11.py` | Cycle 图生成 |
| `scripts/calibrate_mvp11_thresholds.py` | 阈值校准 |
| `scripts/mvp11_hard_gate_eval.py` | Hard Gate 评估 |
| `scripts/run_testbot_scenarios.py` | Testbot 场景运行 |
| `scripts/replay_conversation_tape.py` | 会话回放 |
| `scripts/soak_mvp11.py` | 浸泡测试 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp11/` | 32 | replay, governance, interventions, homeostasis, cycle |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp11/` | run.jsonl, cycle_graph.json, trend data, eval results |
| `artifacts/testbot/` | tape 文件, scenario 结果 |

### 主链接线验证
```python
# emotiond/core.py 导入
from emotiond.governor_v2 import ...
from emotiond.science.cycle import ...
from emotiond.executor_mvp11 import ...
```
**结论**: ✅ 完整接线

---

## MVP11.5: SRAP / 状态主权 / Intent Alignment

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/response_intent_checker.py` | Intent 检查器 | ✅ core.py (shadow) |
| `emotiond/self_report_consistency_checker.py` | 自述一致性检查 | ✅ |
| `emotiond/self_report_interpreter.py` | 自述解释器 | ✅ |
| `emotiond/shadow_analyzer.py` | Shadow 分析 | ✅ |
| `emotiond/numeric_leak_filter.py` | 数值泄漏过滤 | ✅ |

### 脚本
| 文件 | 功能 |
|------|------|
| `scripts/run_testbot_scenarios.py` | 包含 intent alignment 场景 |

### 测试
| 文件 | 描述 |
|------|------|
| `tests/test_response_intent_checker.py` | Intent 检查器测试 |
| `tests/test_adversarial_self_report.py` | 对抗性自述测试 |
| `tests/testbot/test_intent_alignment_e2e.py` | E2E intent 测试 |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp11_5/` | t07_3 结果, shadow 报告 |

### 主链接线验证
```python
# emotiond/core.py
if event.type == "assistant_reply" and event.text:
    from emotiond.response_intent_checker import check_intent
    # shadow mode - 不阻塞主链
```
**结论**: ✅ 接线，运行在 shadow mode

---

## MVP12: Developmental Core Sandbox

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/developmental_core/cycle_engine.py` | Cycle 引擎 | ❓ 未验证 |
| `emotiond/developmental_core/cycle_memory.py` | Cycle 内存 | ❓ 未验证 |
| `emotiond/developmental_core/cycle_metrics.py` | Cycle 指标 | ❓ 未验证 |
| `emotiond/developmental_core/candidate_evaluator.py` | 候选评估器 | ❓ 未验证 |
| `emotiond/developmental_core/hypothesis_generator.py` | 假设生成器 | ❓ 未验证 |
| `emotiond/developmental_core/daemon_integration.py` | 守护进程集成 | ❓ 未验证 |

### 脚本
| 文件 | 功能 |
|------|------|
| `scripts/e2e_test_mvp12.py` | E2E 测试 |
| `scripts/replay_consistency_mvp12.py` | 回放一致性验证 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp12/` | 31 | developmental_core, replay, cycle_memory |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp12/` | cycle_traces/, candidate_pool.json, metrics_history.jsonl |

### 主链接线验证
```bash
$ grep -rn "developmental_core" emotiond/core.py
# (无输出)
```
**结论**: ❌ 未找到主链调用

---

## MVP13: Persistent Self-Model

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/self_model/schema.py` | 新 Schema | ❌ 未使用 |
| `emotiond/self_model/persistence.py` | 持久化 | ⚠️ API 存在 |
| `emotiond/self_model/updates.py` | 更新机制 | ❌ 未使用 |
| `emotiond/self_model/integration.py` | 集成层 | ❌ 未使用 |
| `emotiond/self_model/legacy.py` | Legacy API | ✅ 主用 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp13/` | 21 | self_model_infra, integration, e2e_gate_b |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp13/` | 验证产物 |

### 主链接线验证
```python
# emotiond/core.py
from emotiond.self_model import get_self_model, build_self_model_v0, render_self_report, get_self_model_v0
# 实际使用 legacy API
```
**结论**: ⚠️ 使用 legacy API，新 schema 未生效

### 关键问题
- `TensionType` 枚举不完整，因果干预实验失败

---

## MVP14: Endogenous Drives + Self-Maintenance

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/drives/schema.py` | 新 Drive Schema | ❌ 未使用 |
| `emotiond/drives/manager.py` | DriveManager | ❌ 未使用 |
| `emotiond/drives/integration.py` | 集成层 | ❌ 未使用 |
| `emotiond/drive_homeostasis.py` | Legacy Drive | ✅ 主用 |
| `emotiond/homeostasis.py` | 稳态模块 | ✅ 主用 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp14/` | 12 | drive_infra, drive_integration, e2e_gate_b |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp14/` | 验证产物 |

### 主链接线验证
```python
# emotiond/core.py
from emotiond.drive_homeostasis import (...)
# 使用旧实现，而非 drives/manager.py
```
**结论**: ❌ 新模块未接线，使用 legacy

### 因果验证结果
- ✅ Legacy drive 有因果效力 (实验证明)
- ❌ DriveManager 无持久化机制

---

## MVP15: Reflective Self / Counterfactual Self

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/reflection_engine/schema.py` | 新 Schema | ❌ 未使用 |
| `emotiond/reflection_engine/engine.py` | 新引擎 | ❌ 未使用 |
| `emotiond/reflection.py` | Legacy 反思 | ✅ 主用 |
| `emotiond/self_counterfactual.py` | 反事实模块 | ⚠️ 存在 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp15/` | 9 | reflection_infra |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp15/` | 验证产物 |

### 主链接线验证
```python
# emotiond/core.py
from emotiond.reflection import run_reflection
# 使用旧实现，而非 reflection_engine/
```
**结论**: ❌ 新模块未接线

### 关键问题
- `generate_proposal` 方法不存在，因果链断裂

---

## MVP16: Open Developmental Self

### 核心模块
| 文件 | 描述 | 主链调用 |
|------|------|---------|
| `emotiond/developmental/schema.py` | Schema | ❌ 未使用 |
| `emotiond/developmental/manager.py` | DevelopmentalManager | ❌ 未使用 |

### 脚本
| 文件 | 功能 |
|------|------|
| `tools/mvp16_daily_check.py` | 每日检查脚本 |

### 测试
| 目录 | 测试数 | 覆盖范围 |
|------|--------|---------|
| `tests/mvp16/` | 30 | developmental, persistence, anti-false-positive |

### Artifacts
| 目录 | 内容 |
|------|------|
| `artifacts/mvp16/` | GATE_A/B/C 报告 |
| `artifacts/mvp16-observation/` | 每日观测报告 |

### 主链接线验证
```bash
$ grep -rn "DevelopmentalManager\|developmental" emotiond/core.py
# (无输出)
```
**结论**: ❌ 完全未接线

### 观测状态
- 持久化机制: ✅ 已修复
- 真实数据: ❌ 无
- 状态: `blocked` (insufficient_evidence)

---

## 关键发现总结

### 1. 主链接线问题
| 阶段 | 新模块 | 主链调用 | 实际使用 |
|------|--------|---------|---------|
| MVP13 | self_model/ | ❌ | legacy.py |
| MVP14 | drives/ | ❌ | drive_homeostasis.py |
| MVP15 | reflection_engine/ | ❌ | reflection.py |
| MVP16 | developmental/ | ❌ | N/A |

### 2. 测试覆盖但主链未验证
所有阶段测试通过，但测试只验证模块内部逻辑，未验证与 core.py 的集成。

### 3. Legacy 依赖
MVP13-15 的新模块均未接入主链，主链继续使用旧实现文件。

### 4. 导入冲突 (已修复)
`emotiond/drives.py` (文件) 与 `emotiond/drives/` (目录) 命名冲突，已通过 importlib 修复。

---

*审计完成时间: 2026-03-13*
