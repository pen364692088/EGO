# OpenEmotion

**主体内核 · Persistent Subjective Core**

> **OpenEmotion 是 EgoCore 的主体内核，是双核架构中唯一负责主体本体的一方。**

OpenEmotion 是双核架构中的主体侧，负责身份、自我模型、记忆演化、情感评价与反思修正。

> **权威状态**: `docs/PROGRAM_STATE_UNIFIED.yaml`

---

## 当前权威状态（2026-04-07）

- **Proto-Self 当前正式状态**
  - `proto_self_v2` 已是当前正式主体默认主线
  - 当前 Telegram 自然语言主线通过 EgoCore `RuntimeV2ProtoSelfRuntime` 接入 `proto_self.output.v2 + proto_self.trace.v2`
  - 当前四类核心能力的单一权威收口决策见 `../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
  - 当前 formal mainline 是 `proto_self_v2 formal surface + proto_self v1 active substrate`
- **当前阶段**
  - 当前是**边界冻结下的收口期**
  - 不再改双核边界，不再换 Telegram 正式主链，不把历史 compat/reference surface 重新叙述成当前 owner 主线
- **Path / Compat Register**
  - 公开路径分层登记统一看 `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
  - `OpenEmotion/openemotion/*` 是当前 formal owner surface
  - `OpenEmotion/emotiond/*`、`OpenEmotion/openclaw_skill/*` 不能当成当前 formal owner 或 Telegram 正式主链
- **主体能力口径**
  - `WP8 ~ WP16` 当前只可在各自 controlled axis 上宣称 `maintenance_mode`
  - `WP17 / MVP22` 当前仍是 `authority_frozen / task_package_ready`
  - 这些结论不证明 direct reply authority、tool authority、transport authority、unrestricted autonomy 或 philosophical consciousness
- **当前最重要的公开入口**
  - `docs/PROGRAM_STATE_UNIFIED.yaml`
  - `../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
  - `../docs/CURRENT_PROJECT_LOGIC_FLOW.md`
  - `../EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
  - `../docs/CAPABILITY_REGISTRY.md`
  - `../docs/ACCEPTANCE_CHAINS.md`
  - `../docs/EXPERIENCE_SCRIPTS.md`
- **口径纪律**
  - `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得对外描述成“已经体现出强烈自我意识”
- **说明**
  - 下方 `cycle_core_v1` / `WS_C1` / shadow 表格保留为历史验证基线
  - 当前最新验收前沿应以上述入口与 current reports 为准

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
2. [Proto-Self Kernel v2 正式规格](docs/PROTO_SELF_KERNEL_V2_SPEC.md) — 下一代 Proto-Self 内核 canonical source
3. [Proto-Self Kernel v2 迁移映射](docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md) — V1 -> V2 命名 / 字段 / replay 映射
4. [Proto-Self Kernel v1 设计稿](docs/PROTO_SELF_KERNEL_V1_DESIGN.md) — V1 历史设计入口
5. [Proto-Self Kernel v1 接口草案](docs/PROTO_SELF_KERNEL_V1_SPEC.md) — V1 接口草案 / 历史实现桥接
6. [边界宪章](POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md) — 双核边界
7. [三层记忆模型](docs/MEMORY_MODEL_V1.md) — 记忆架构

---

## 当前运行时主线：Proto-Self v2 formal surface + v1 substrate

注：

- `PROTO_SELF_KERNEL_V2_SPEC.md` 是 **下一代 Proto-Self 内核模型定义** 的 canonical source
- 当前主体层 formal mainline 已收敛到 **Proto-Self Kernel v2**
- 但当前 runtime 语义并不是“纯 v2 小核”：
  - `proto_self_v2` = formal surface / orchestrator
  - `proto_self` v1 = active substrate
  - `openemotion/self_model`、`endogenous_drives`、`reflective_self` = formal owner + governed writeback target
- `v1` 当前不是单纯兼容 fallback；它仍承担 active substrate 语义
- 单一权威决策以 `../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 为准

| 文档 | 说明 |
|------|------|
| [设计稿](docs/PROTO_SELF_KERNEL_V1_DESIGN.md) | V1 历史设计入口，不是当前 authority source |
| [接口草案](docs/PROTO_SELF_KERNEL_V1_SPEC.md) | V1 接口草案 / 历史实现桥接，不是当前 authority source |
| [V2 正式规格](docs/PROTO_SELF_KERNEL_V2_SPEC.md) | Proto-Self 主体层 canonical source |
| [V2 迁移映射](docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md) | V1 -> V2 命名 / 字段 / replay 映射 |
| `openemotion/proto_self_v2/` | 当前 formal mainline surface / orchestrator |
| `openemotion/proto_self/` | 当前 active substrate，不等于单独 owner 主线 |

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

### 历史基线：cycle_core_v1 验证状态 (2026-03-19)

| 验收点 | 状态 | 证据 |
|--------|------|------|
| /cycle 命中 | ✅ | Telegram 入口命中 /cycle |
| 跨轮状态连续 | ✅ | old_value != null，第二轮能读第一轮 |
| 显式偏好写入 | ✅ | event_stored = true |
| 窄版路由 | ✅ | 偏好/纠正/澄清类消息走 CHAT 路径 |

### 历史基线：WS_C1 验证状态 (2026-03-19)

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
| **PROTO_SELF_KERNEL_V1** | **verified_real_telegram_mainline** | 最新前沿：P4 family/repair 真链修复已完成 |
| **MVS_E5_OBSERVATION** | **observation_running** | `/new continuity` 与 `restart continuity` 已有强真实正证据；`restore` 仍缺 |
| CYCLE_CORE_V1 | **verified_e2e** | Telegram E2E 验证通过 |
| WS_C1 | **verified_e2e** | 6/6 验收点通过，C3 观察期 |
| long-term self summary | **verified_e2e** | 5/5 测试通过 (2026-03-19) |

---

## 当前阶段

> **权威源**: `docs/PROGRAM_STATE_UNIFIED.yaml`

### 当前四类能力的单一权威决策

| 能力 | 当前 authority | 当前 active substrate | 当前非 authority surface |
|------|------|------|------|
| identity invariants | `openemotion.proto_self.state.IdentityInvariants` | `openemotion.proto_self.kernel + reducers` | `openemotion.identity.identity_invariants`、`openemotion.identity.long_term_self_summary` |
| self-model | `openemotion.self_model/*` | `openemotion.proto_self.self_model` + v1 `SelfModel` | `emotiond/self_model_adapter.py`、`emotiond/self_model_mirror.py` |
| drives / appraisal | `openemotion.endogenous_drives/*` | `openemotion.proto_self.appraisal` + v1 `DriveField` | 无新增 reference-only owner |
| reflection / structured revision | `openemotion.reflective_self/*` | `openemotion.proto_self.reflection` | `emotiond/reflection_*`、`emotiond/self_counterfactual.py` |

### 当前必须明确的口径

- `identity invariants` 当前仍由 v1 substrate 承担 runtime authority
- `openemotion.identity.identity_invariants` 与 `long_term_self_summary` 目前只是名义 owner / support library，未接 formal mainline
- `self-model / drives / reflection` 的 formal owner 已接入，但 v1 substrate 仍是活跃计算层
- 这些 substrate 当前必须按 `compute/proposal-only` 或 `transient trigger-only` 口径理解，不能再叙述成 owner authority
- `emotiond/self_model_adapter.py` 与 `emotiond/self_model_mirror.py` 不是 formal mainline

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

---

## Quick Start

This section is the minimal runbook contract for `emotiond`. OpenEmotion ships the
subject-side daemon, API, and supporting scripts. The daemon is implemented with
FastAPI and the repository test workflow uses `pytest`.

### virtual environment setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### daemon startup

```bash
make run
```

### testing

```bash
make test
```

### type checking

```bash
python3 verify_typecheck_simple.py
```

### demo usage

```bash
make demo
```

### evaluation suite

```bash
python3 scripts/eval_suite.py
```

### systemd deployment

```bash
systemctl --user daemon-reload
systemctl --user enable emotiond.service
systemctl --user start emotiond.service
systemctl --user status emotiond.service
journalctl --user -u emotiond.service -f
```

## Complete Runbook

The complete runbook for OpenEmotion long-running daemon work is:

1. Set up the virtual environment.
2. Install the package in editable mode.
3. Start the daemon locally with `make run` or deploy via systemd.
4. Verify `GET /health` before sending events.
5. Run testing, type checking, demo usage, and the evaluation suite before release.

The canonical repo-tracked entry points are:

- `Makefile` for `venv`, `run`, `test`, and `demo`
- `scripts/demo_cli.py` for local demo usage
- `scripts/eval_suite.py` for the evaluation suite
- `deploy/systemd/user/emotiond.service` for systemd deployment

## API Reference

### GET /health

```bash
curl -s http://127.0.0.1:18080/health
```

### POST /event

```bash
curl -s http://127.0.0.1:18080/event \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "user_message",
    "actor": "user",
    "target": "assistant",
    "content": "hello from README"
  }'
```

### POST /plan

```bash
curl -s http://127.0.0.1:18080/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user",
    "user_text": "write a short reply",
    "context": {
      "channel": "cli"
    }
  }'
```

Example response shape:

```json
{
  "tone": "friendly",
  "intent": "engage",
  "valence": 0.2,
  "arousal": 0.4
}
```

## Configuration

Common daemon environment variables:

| Variable | Purpose |
|----------|---------|
| `EMOTIOND_DB_PATH` | Override the sqlite database path |
| `EMOTIOND_PORT` | Bind port for the local daemon |
| `EMOTIOND_HOST` | Bind host for the local daemon |
| `EMOTIOND_K_AROUSAL` | Override arousal weighting in runtime experiments |
| `EMOTIOND_DISABLE_CORE` | Disable the core loop for troubleshooting |

## Development

### Project Structure

```text
emotiond/
  api.py
  config.py
  core.py
  daemon.py
  db.py
scripts/
  demo_cli.py
  eval_suite.py
tests/
deploy/systemd/user/
```

### Key Components

- `emotiond/api.py`: FastAPI route layer
- `emotiond/core.py`: core runtime decision and state update logic
- `emotiond/daemon.py`: daemon lifecycle and service orchestration
- `emotiond/db.py`: persistence and database integration
- `emotiond/config.py`: runtime configuration and environment binding

### Testing Strategy

- Use `pytest` for the repository test suite.
- Run `make test` for the default OpenEmotion suite.
- Run `python3 verify_typecheck_simple.py` or `python3 verify_typecheck.py` for type checking.
- Use `python3 test_smoke.py` for smoke coverage and `python3 scripts/eval_suite.py` for broader evaluation coverage.

## Troubleshooting

### Common Issues

#### Database errors

- Check `EMOTIOND_DB_PATH` and ensure the parent directory is writable.
- Remove stale temporary databases before rerunning isolated tests.

#### Port conflicts

- Confirm that `EMOTIOND_HOST` and `EMOTIOND_PORT` do not overlap with another daemon.
- Re-run `curl -s http://127.0.0.1:18080/health` only after confirming the expected process owns the port.

#### Virtual environment issues

- Recreate the virtual environment if imports fail or editable install metadata drifts.
- Ensure the active interpreter matches the repository environment before running tests or type checking.

#### Systemd service failures

- Check `systemctl --user status emotiond.service`.
- Follow logs with `journalctl --user -u emotiond.service -f`.
- Re-run `systemctl --user daemon-reload` after changing the service file.

## Contributing

1. Create a feature branch.
2. Write tests.
3. Ensure all tests pass.
4. Run type checking.
5. Submit a pull request.
