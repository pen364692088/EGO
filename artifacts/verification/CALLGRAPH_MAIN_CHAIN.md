# Callgraph: Main Chain

> 主处理链调用图 | 独立真实性审计

---

## 核心入口点

### 1. HTTP API 入口 (`emotiond/api.py`)

```
POST /event → process_event(event)
POST /plan  → generate_plan(request)
```

### 2. 主处理函数 (`emotiond/core.py`)

```
process_event(event)
└── EmotionState.update_from_event()
└── RelationshipManager.update_from_event()
└── memory_system.get_memory_impact_on_relationship()
└── episodic_memory_manager.observe_event()
└── body_state.update_from_event()
└── ledger.record_promise()
└── ledger.detect_violation()
└── get_precision_controller()
└── get_self_model_v0() ← MVP13 legacy
└── run_reflection() ← MVP15 legacy
└── check_intent() ← MVP11.5
└── update_state()
└── update_relationship()
└── record_budget_trace()

generate_plan(request)
└── get_state()
└── select_action_with_explanation()
│   └── get_self_model_v0() ← MVP13 legacy
│   └── get_persistence_constraint()
│   └── save_decision()
└── get_self_model_v0() ← MVP13 legacy
└── render_self_report() ← MVP13 legacy
└── interpret_to_intent_contract() ← MVP11.5
```

---

## 模块调用矩阵

| 调用方 | 被调用模块 | 新模块 (MVP13-16) | 旧模块 | 状态 |
|--------|-----------|------------------|--------|------|
| core.py | self_model | `self_model/__init__.py` (re-export legacy) | `self_model/legacy.py` | ⚠️ 部分接线 |
| core.py | reflection | ❌ 未调用 `reflection_engine/` | `reflection.py` | ❌ 未接线 |
| core.py | drives | ❌ 未调用 `drives/` | `drive_homeostasis.py` | ❌ 未接线 |
| core.py | developmental | ❌ 未调用 `developmental/` | N/A | ❌ 未接线 |

---

## 详细调用图

### MVP13 (self_model) 调用链

```
emotiond/core.py
│
├── Line 42: from emotiond.self_model import ...
│   │
│   └── emotiond/self_model/__init__.py
│       │
│       ├── from .legacy import (...)  ← 实际使用的路径
│       │   └── emotiond/self_model/legacy.py
│       │       └── SelfModelV0, build_self_model_v0, render_self_report
│       │
│       └── from .schema import (...)  ← 未被 core.py 使用
│           └── emotiond/self_model/schema.py
│               └── SelfModelState, IdentityCore, etc.
│
├── Line 827: self_model_v0 = get_self_model_v0(target)
│   └── emotiond/self_model/legacy.py:get_self_model_v0()
│
└── Line 845: self_report = render_self_report(self_state_v0, ...)
    └── emotiond/self_model/legacy.py:render_self_report()
```

### MVP14 (drives) 调用链

```
emotiond/core.py
│
├── Line 67: from emotiond.drive_homeostasis import ...
│   │
│   └── emotiond/drive_homeostasis.py  ← 旧文件
│       └── DriveState, drive_error, emotion_from_drive
│
├── emotiond/drives/  ← 新模块，未被 core.py 调用
│   ├── manager.py (DriveManager)
│   ├── schema.py (DriveState, ActiveDrive)
│   └── integration.py
│
└── 无任何调用到 drives/manager.py 或 drives/schema.py
```

### MVP15 (reflection) 调用链

```
emotiond/core.py
│
├── Line 22: from emotiond.reflection import run_reflection
│   │
│   └── emotiond/reflection.py  ← 旧文件
│       └── run_reflection()
│
├── emotiond/reflection_engine/  ← 新模块，未被 core.py 调用
│   ├── engine.py (ReflectionEngine)
│   └── schema.py (ReflectionState, ReflectionJob)
│
└── 无任何调用到 reflection_engine/engine.py
```

### MVP16 (developmental) 调用链

```
emotiond/core.py
│
└── 无任何 developmental 相关导入或调用

emotiond/api.py
│
└── 无任何 developmental 相关导入或调用

tools/mvp16_daily_check.py  ← 独立脚本，不接入主链
│
├── from emotiond.developmental import ...
│   └── emotiond/developmental/manager.py
│
└── reset_developmental_manager()  ← 每次检查前重置
```

---

## 未接线模块统计

| 模块 | 文件数 | 函数/类 | core.py 调用次数 |
|------|--------|---------|-----------------|
| `emotiond/self_model/` (新) | 5 | ~20 | 0 (legacy: 4) |
| `emotiond/drives/` | 4 | ~15 | 0 |
| `emotiond/reflection_engine/` | 3 | ~10 | 0 |
| `emotiond/developmental/` | 3 | ~10 | 0 |

---

## 结论

1. **MVP13**: 新 schema 未使用，仅通过 legacy 兼容层使用旧实现
2. **MVP14/15/16**: 新模块零调用，主链完全未接线
3. **架构分层宣称未实现**: 文档宣称的 Layer 4/5/6/7 未在代码中体现

---

*调用图证据: grep 零匹配 + 导入分析*
