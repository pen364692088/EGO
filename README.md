# OpenEmotion

**主体内核 · Persistent Subjective Core**

> **OpenEmotion 是 EgoCore 的主体内核，是双核架构中唯一负责主体本体的一方。**

OpenEmotion 是双核架构中的主体侧，负责身份、自我模型、记忆演化、情感评价与反思修正。

> **权威状态**: `docs/PROGRAM_STATE_UNIFIED.yaml`

---

## 定位

| 角色 | 说明 |
|------|------|
| **主体内核** | 定义"它是谁、如何变化、如何理解自己、如何被经历塑造" |
| **权威源** | identity invariants、self-model、long-term self summary、memory、appraisal、reflection 的最终解释权 |
| **协同宿主** | 通过 EgoCore 宿主与世界交互 |

### 边界

| OpenEmotion 负责 | EgoCore 负责 |
|------------------|--------------|
| identity invariants | 用户入口 |
| self-model | 运行时 |
| long-term self summary | 任务系统 |
| event / narrative / policy memory | 工具执行 |
| appraisal / reflection | 恢复 orchestration |
| | adapter / audit / trace |

**允许 mirror / cache / shim，不允许双主。**

---

## 新 Agent 阅读顺序

1. 本 README — 定位与边界
2. [Proto-Self Kernel v1 设计稿](docs/PROTO_SELF_KERNEL_V1_DESIGN.md) — MVS 内核设计
3. [Proto-Self Kernel v1 接口草案](docs/PROTO_SELF_KERNEL_V1_SPEC.md) — 接口与伪代码
4. [边界宪章](POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md) — 双核边界
5. [三层记忆模型](docs/MEMORY_MODEL_V1.md) — 记忆架构

---

## 当前正式主线：Proto-Self Kernel v1

| 文档 | 说明 |
|------|------|
| [设计稿](docs/PROTO_SELF_KERNEL_V1_DESIGN.md) | 最小主体内核设计稿（MVS 内核候选） |
| [接口草案](docs/PROTO_SELF_KERNEL_V1_SPEC.md) | 接口与伪代码草案 |

### 核心主张

> **Proto-Self 的本体核应该尽量小：一个统一递归更新器 + 少量高价值状态 + 明确后果回流。**

最小闭环：**事件进入 → 内态更新 → 生成倾向 → 经过 EgoCore 裁决 → 结果回流 → 强化/削弱自我不变量**

---

## 当前验证状态

| 主线 | 状态 | 说明 |
|------|------|------|
| MVS | active | Minimum Viable Self |
| **cycle_core_v1** | **verified_telegram_e2e** | 循环主体核 v1，已通过 Telegram E2E 验证 |
| **WS_C1** | **verified_e2e** | 三层记忆模型已验证，C3 观察期 |

### cycle_core_v1 验证状态 (2026-03-19)

| 验收点 | 状态 | 证据 |
|--------|------|------|
| /cycle 命中 | ✅ | Telegram 入口命中 /cycle |
| 跨轮状态连续 | ✅ | old_value != null，第二轮能读第一轮 |
| 显式偏好写入 | ✅ | event_stored = true |
| 窄版路由 | ✅ | 偏好/纠正/澄清类消息走 CHAT 路径 |

### WS_C1 验证状态 (2026-03-19)

| 验收点 | 状态 | 证据 |
|--------|------|------|
| 偏好写入 | ✅ | event_stored = true |
| 目标写入 | ✅ | event_stored = true |
| 约束写入 | ✅ | salience 阈值过滤 |
| 第二轮读取 | ✅ | policy_hint confidence > 0.5 |
| 闲聊不误写 | ✅ | event_stored = false |
| 纠正覆盖 | ✅ | 检测到覆盖痕迹 |

**C1 验证**: 6/6 通过，进入 C3 观察期

## 当前状态

| 能力 | 状态 | 说明 |
|------|------|------|
| **PROTO_SELF_KERNEL_V1** | **verified_mainline_e2e** | 主链 E2E 验证通过 (2026-03-22) |
| CYCLE_CORE_V1 | **verified_e2e** | Telegram E2E 验证通过 |
| WS_C1 | **verified_e2e** | 6/6 验收点通过，C3 观察期 |
| long-term self summary | **verified_e2e** | 5/5 测试通过 (2026-03-19) |

---

## 当前阶段

> **权威源**: `docs/PROGRAM_STATE_UNIFIED.yaml`

### ✅ 已验证

| 阶段 | 状态 | 证据 |
|------|------|------|
| identity invariants | verified_contract | openemotion/identity/ |
| self-model v1 | verified_contract | openemotion/self_model/ |
| SelfModelAdapter (主链 wiring) | verified_e2e | emotiond/self_model_adapter.py, docs/E2E_SELF_MODEL_ADAPTER_REPORT.md |

### 🔄 Shadow Mode 运行中

| 阶段 | 状态 | 说明 |
|------|------|------|
| MVP13 (SelfModel) | shadow_running | 已接入主链，E2E 验证通过 |
| MVP14 (Drives) | shadow_running | Gate A/B passed |
| MVP15 (Reflection) | shadow_running | Persistence integrity verified |

### ✅ 已验证 (E2E)

| 阶段 | 状态 | 说明 |
|------|------|------|
| long-term self summary | **verified_e2e** | tools/test_long_term_self_summary_e2e.py |
| WS_C1 三层记忆模型 | **verified_e2e** | artifacts/eval/ws_c1_verification_20260319.md |

### 📋 下一步

| 阶段 | 优先级 | 状态 |
|------|--------|------|
| C3 观察期 | P0 | 7 天稳定性监控 (2026-03-19 → 2026-03-26) |
| v1.1.0 shim 清理 | P1 | 删除 8 个 shim |
| 监控 shadow mode 稳定性 | P2 | 持续进行 |

---

## 架构

```
openemotion/
├── proto_self/                   # Proto-Self Kernel v1 (新增)
│   ├── kernel.py                 # 主循环 process_event()
│   ├── schemas.py                # KernelEvent / KernelOutput
│   ├── state.py                  # ProtoSelfState (4+1 状态)
│   ├── appraisal.py              # drive_field 更新
│   ├── self_model.py             # self_model 更新
│   ├── cycles.py                 # cycle 固化
│   ├── reflection.py             # 反思触发
│   ├── reducers.py               # 状态写回
│   └── tests/                    # 25 个单元测试
├── identity/
│   ├── identity_invariants.py    # 身份不变量
│   └── long_term_self_summary.py # 长期自我摘要
├── self_model/
│   └── model.py                  # 自我模型
├── memory/
│   ├── event_memory.py           # 事件层（不可变）
│   ├── narrative_memory.py       # 叙事层（可变）
│   └── policy_memory.py          # 策略层（生命周期）
└── __init__.py

schemas/
├── identity_invariants.schema.json
├── self_model.schema.json
├── long_term_self_summary.schema.json
├── event.schema.json
├── narrative.schema.json
└── policy.schema.json
```

---

## 三层记忆模型 v1

```
┌─────────────────────────────────────┐
│         Policy Memory               │
│   长期偏好/约束/原则                 │
│   ↑ 提炼自叙事                       │
├─────────────────────────────────────┤
│       Narrative Memory              │
│   结构化叙事                         │
│   ↑ 聚合自事件                       │
├─────────────────────────────────────┤
│         Event Memory                │
│   原始事件（不可变）                 │
└─────────────────────────────────────┘
```

详见 `docs/MEMORY_MODEL_V1.md`。

---

## 快速开始

### 前置条件

- Python 3.10+
- EgoCore 宿主已部署

### 安装

```bash
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 验证模块

```python
from openemotion.memory import EventMemory, NarrativeMemory, PolicyMemory
from openemotion.identity import IdentityInvariants
from openemotion.self_model import SelfModel

# 创建事件
em = EventMemory()
event = em.create(EventType.USER_MESSAGE, "Hello")

# 创建叙事
nm = NarrativeMemory()
narrative = nm.create(NarrativeType.PROJECT_PROGRESS, "My Project", "Summary", [event.id])

# 提议策略
pm = PolicyMemory()
policy = pm.propose("Be Concise", "Keep responses brief", PolicyType.PREFERENCE)
```

---

## 测试

```bash
# 运行所有测试
make test

# 类型检查
mypy openemotion/
```

---

## 边界宪章

从 WS-C/C1 起，以下规则强制执行：

1. **memory model / salience / consolidation / relationship semantics / appraisal / reflection semantics 禁止写入 EgoCore**
2. 新功能开写前必须写六问门禁
3. 未通过 Boundary Gate A/B/C 的模块不得接入主链

详见 `POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md`。

---

## 相关仓库

| 仓库 | 角色 |
|------|------|
| [EgoCore](../EgoCore) | 宿主、运行时、执行、治理 |

---

## License

MIT
