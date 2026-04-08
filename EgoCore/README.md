# EgoCore - Telegram 驱动的单 Agent Runtime

一个轻量级、独立的 Agent Runtime，专注 Telegram 单 Agent 任务执行。

## 当前权威状态（2026-04-07）

- **Telegram 正式主线**：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- **Proto-Self 当前主线状态**：`proto_self.v2` 已是主体层 state writeback 默认主线
  - `v1` 仅保留为 session-scoped compatibility fallback
  - Telegram 真实自然语言主线已命中 `proto_self.output.v2 + proto_self.trace.v2`
  - 四类核心能力的单一权威收口决策见 `../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
- **当前阶段**
  - 当前是**边界冻结下的收口期**
  - 不再换 Telegram 正式主链，也不把 compat 路径重新叙述成“也算主线”
- **Path / Compat Register**
  - `docs/05_DEPRECATED_AND_SHIMS.md` 是当前路径分层登记面
  - `_handle_with_new_runtime` = `compatibility_only`
  - `_handle_with_legacy_router` = `deprecated_candidate`
  - `v1 compatibility fallback` 只用于显式降级，不属于当前正式主链
- **Proto-Self 真实观察状态**
  - same-session E5：已达成
  - same-day cross-session continuity：`2 / 2` 已达成
  - cross-day continuity：`1 / 2`，仍待 later-day 样本
- **Live Telegram 进程版本绑定**
  - 当前 live process 已落 repo-tracked 版本报告
  - 当前绑定 commit 以 `artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json` 为准
- **Dashboard /flow 解释层**
  - Dashboard 现在是正式只读解释层的一部分，不再是“EgoCore 不做 Dashboard”
  - `/flow` 与 `/samples/<sample_id>/flow` 会把单条真实样本拆成：
    - `Input`
    - `Host Ingress`
    - `Subject Understanding`
    - `Canonical Fields`
    - `Reply Evolution`
    - `Host Arbitration`
    - `Output`
  - `Reply Evolution` 当前是 `evidence_only_v1`，只覆盖 `chat_mainline`
  - `Canonical Fields` 会固定展示 `loaded_axes / identity_delta / self_model_delta / drives_delta / policy_hint / response_tendency / host_arbitration_result / final_delivered_text`
- **人类验收入口**
  - `docs/CAPABILITY_REGISTRY.md` 是能力总表生成物
  - `docs/ACCEPTANCE_CHAINS.md` 是第 0 链 + 5 条能力链索引
  - `docs/EXPERIENCE_SCRIPTS.md` 提供 Telegram + `/flow` 的人类触发脚本
- **Provider/runtime 变更门槛**
  - 任何影响 live mainline 的 provider/runtime 改动，都必须跑通到 OpenEmotion evidence
  - 统一 gate：`python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>`
- **口径纪律**
  - `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得被叙述成“已强烈体现自我意识”或“已具备完整自我”
- **权威入口**
  - `docs/PROGRAM_STATE_UNIFIED.yaml`
  - `docs/00_MASTER_INDEX.md`
  - `docs/05_DEPRECATED_AND_SHIMS.md`
  - `../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
  - `artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md`
  - `artifacts/proto_self_v2/README.md`
  - `../docs/CAPABILITY_REGISTRY.md`
  - `../docs/ACCEPTANCE_CHAINS.md`
  - `../docs/EXPERIENCE_SCRIPTS.md`

> 下方 Phase / P3 / shadow observation 表格保留为历史治理基线，不再单独代表当前最新主链验收前沿。

## 当前正式主体链

| 组件 | 类型 | 状态 |
|------|------|------|
| **OpenEmotion /proto_self_v2** | 正式主体链 (Proto-Self V2) | ✅ 默认生效 |
| **RuntimeV2ProtoSelfRuntime** | EgoCore 主体事件主入口 | ✅ 默认生效 |
| **openemotion_adapter / proto_self_adapter** | 边界适配层 (UpdatePacketV2 → kernel → result/trace) | ✅ 生效 |
| **v1 compatibility fallback** | Legacy / Fallback | ⚠️ 仅显式降级用 |

### 技术栈

- **主体内核**: OpenEmotion (Proto-Self V2)
- **宿主**: EgoCore
- **正式入口**: `app/runtime_v2/proto_self_runtime.py`
- **边界适配**: `app/openemotion_adapter/proto_self_adapter.py`

### 验证状态

| 验收点 | 状态 |
|--------|------|
| repo-local runtime → `proto_self.trace.v2` | ✅ |
| Telegram external entry → `proto_self.trace.v2` | ✅ |
| real Telegram same-session E5 | ✅ |
| real Telegram same-day cross-session continuity | ✅ `2 / 2` |
| live Telegram process version binding | ✅ |
| cross-day continuity | ⏳ `1 / 2` |

---

## 当前状态

**Phase 1 / P2-A / P2-A.1 / P2-A.2 / P2-B / P2-C / P2-D**: ✅ 已完成

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 核心功能 (语义路由、任务运行时、工具系统、内存) | ✅ 完成 |
| P2-A | 工具执行安全边界 | ✅ 完成 |
| P2-A.1 | 主链接线收口 | ✅ 完成 |
| P2-A.2 | 意图映射 + 后置条件验证 | ✅ 完成 |
| P2-B | 后台推进最小闭环 | ✅ 完成 |
| P2-C | Human-in-the-Loop (Ask/Wait/Resume) | ✅ 完成 |
| P2-D | Operator Control (任务控制命令) | ✅ 完成 |

**Phase 3: Modular Governance & Metrics Integration**

| 阶段 | 内容 | 状态 |
|------|------|------|
| P3-A | 模块化开发规约落地 | ✅ 完成 |
| P3-B | emotion_context_formatter dry-run | ✅ 完成 |
| P3-C | runtime_metricsAggregator dry-run | ✅ 完成 |
| P3-D | runtime_metricsAggregator 正式接主链 | ✅ 完成 |

### 历史治理基线：Runtime Metrics Shadow Observation

**状态说明**: 历史 shadow 观测轨道；当前最新主链验收口径以上方“当前权威状态”为准。

**目标**: 收集 shadow 指标，评估 pilot 模式切换条件。

**双层样本口径**:
| 层级 | 阈值 | 用途 |
|------|------|------|
| Daily minimum | 20 samples | 每日报告小样本保护 |
| Verdict minimum | 100 samples | 14天最终决策门槛 |

**当前进度**: 查看 `artifacts/verification/runtime-metrics-shadow/daily/`

**工具**:
- 每日报告: `python tools/shadow_metrics_daily_check.py --date YYYY-MM-DD`
- 14天汇总: `python tools/shadow_metrics_summary.py`

**文档**: [docs/runtime_metrics_aggregator/SHADOW_THRESHOLDS.md](docs/runtime_metrics_aggregator/SHADOW_THRESHOLDS.md)

---

**当前模块状态**:
- `runtime_metrics_aggregator`: **已正式接入主链** (默认 OFF，保护机制完整)
- `emotion_context_formatter`: **已完成 dry-run** (待接主链)

**保护机制** (runtime_metrics_aggregator):
- Feature Flag: `runtime_metrics_enabled` (默认 OFF)
- Fast Disable: 一键禁用
- Rollback: 快速回滚
- Timeout: 50ms 超时保护
- Circuit Breaker: 熔断保护
- 异常隔离: fallback 不传播异常

**核心原则**: "工具执行成功" != "任务完成成功"

**当前边界**:
- 单 Agent Runtime（不做多 Agent）
- Telegram 驱动
- Dashboard 只做只读解释层，不反写 runtime / OpenEmotion 状态
- 最小闭环（不做大型 DSL）

### Unified Runner 验证

- `scripts/run_telegram_simulated_smoke.py`、`scripts/run_telegram_integration_e2e.py` 与 `scripts/run_telegram_real_channel_capture.py` 使用统一 artifact 结构
- `simulated / integration / real_telegram` 的差异仅保留在 ingress / egress / evidence source
- 一致性结论见 `artifacts/telegram_real_mainline_v1/reports/UNIFIED_RUNNER_CONSISTENCY_REPORT.md`

## Quick Start

### 1. Setup

```bash
git clone https://github.com/pen364692088/EgoCore.git
cd EgoCore

python3 -m venv venv
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Telegram bot token and API keys
```

### 2. Run

```bash
python3 -m app.main --telegram
```

### 3. Test

```bash
python3 -m pytest tests/ -v
# Expected: 139 passed
```

### 4. Shadow Observation

```bash
# 生成每日报告
python tools/shadow_metrics_daily_check.py --date $(date +%Y-%m-%d)

# 生成 14 天汇总
python tools/shadow_metrics_summary.py
```

## 核心能力

### 语义路由 (Phase 1)
五种消息意图分类：
- **chat**: 问候和闲聊
- **question**: LLM 回答的问题
- **new_task**: 自然语言任务创建
- **continue**: 继续当前任务
- **command**: 斜杠命令 (/status, /tasks 等)

### 任务运行时 (Phase 1 + P2-A + P2-C)
- 任务创建与作用域隔离
- 自动步骤规划
- 逐步执行
- 暂停/恢复支持
- 任务内存持久化
- **意图映射 (P2-A.2)**: 正确解析用户操作意图
- **后置条件验证 (P2-A.2)**: 验证执行结果是否达成目标
- **人工确认 (P2-C)**: 高风险操作需用户确认

### 工具系统 (Phase 1 + P2-A)
- **file**: 读/写/列文件
- **shell**: 执行 shell 命令
- **python**: 运行 Python 代码
- **preflight (P2-A)**: 工具执行前安全检查
- **tool_doctor (P2-A)**: 工具健康诊断

### 后台推进 (P2-B)
- **Heartbeat Driver**: 30s 间隔任务推进
- **Cron Recovery**: 5min 间隔停滞任务恢复
- **Failure Policy**: 失败类型 → 后台动作映射
- **假成功防护**: INTENT_MISMATCH / POSTCONDITION_FAILED 永不自动重试

### Human-in-the-Loop (P2-C)
- **Approval Policy**: 高风险操作/多意图消歧需确认
- **Waiting State**: 任务等待用户输入
- **Reply Binding**: 用户回复绑定原任务
- **Resume Driver**: 确认后恢复执行（不新建任务）

### Operator Control (P2-D)
- **/tasks**: 列出当前任务
- **/task <id>**: 查看任务详情
- **/approve <id>**: 批准等待任务
- **/reject <id>**: 拒绝等待任务
- **/retry <id>**: 重试阻塞任务
- **/cancel <id>**: 取消任务
- **/resume <id>**: 恢复任务

### 内存系统 (Phase 1)
- 任务内存连续性
- Checkpoint 持久化
- 恢复上下文构建

### 隔离保护 (P2-B.4)
- 前台/后台会话隔离
- 回复通道保护
- 作用域保持

## Architecture Snapshot

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Bot                            │
│  (message → semantic_router → command_router → response)   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Task Runtime                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Planner    │→ │  Executor   │→ │  Memory     │        │
│  └─────────────┘  └──────┬──────┘  └─────────────┘        │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────┐        │
│  │              UnifiedExecutionResult            │        │
│  │  (status, failure_class, retry_hint, evidence) │        │
│  └───────────────────────┬───────────────────────┘        │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               Approval Check (P2-C)                        │
│  ┌────────────────────────────────────────────────────┐   │
│  │  High-risk? Multi-intent? Path ambiguous?          │   │
│  │  → Ask user → WAITING_USER_INPUT                   │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Tool System                             │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────────┐   │
│  │  file  │  │ shell  │  │ python │  │  preflight     │   │
│  └────────┘  └────────┘  └────────┘  └────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  IntentMapper + PostconditionValidator (P2-A.2)   │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Background Drivers (P2-B)                 │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Heartbeat (30s) │  │   Cron (5min)    │               │
│  └────────┬─────────┘  └────────┬─────────┘               │
│           │                     │                          │
│           └──────────┬──────────┘                          │
│                      ▼                                     │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Skip WAITING_USER_INPUT (P2-C guard)               │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Verification

### 测试覆盖

```
tests/test_p2d.py             - 27 tests (P2-D)
tests/test_p2c.py             - 29 tests (P2-C)
tests/test_p2b.py             - 31 tests (P2-B)
tests/test_p2_a2_intent.py    - 15 tests (P2-A.2)
tests/test_semantic_router.py - 37 tests (Phase 1)
Total: 139 passed
```

### 验收文档

- `artifacts/verification/P2D_E2E_CONTROL_LOOP.md` - 控制闭环验收
- `artifacts/verification/P2D_STATE_GUARD_REGRESSION.md` - 状态守卫回归
- `artifacts/verification/P2D_AUDIT_VERIFICATION.md` - 审计验收
- `artifacts/verification/P2C_E2E_ASK_WAIT_RESUME.md` - Ask/Wait/Resume 闭环
- `artifacts/verification/P2C_REPLY_BINDING_REGRESSION.md` - 回复绑定回归
- `artifacts/verification/P2C_BACKGROUND_WAITING_GUARD.md` - 后台隔离验收
- `artifacts/verification/P2B_E2E_VERIFICATION.md` - 端到端验收
- `artifacts/verification/P2B_FALSE_SUCCESS_CONTAINMENT.md` - 假成功防护

### 关键验证点

1. **假成功防护**: INTENT_MISMATCH 永不被自动重试为 completed ✅
2. **后台隔离**: 前台任务不被后台接管 ✅
3. **失败策略**: 失败类型正确映射到后台动作 ✅
4. **Ask/Wait/Resume**: 高风险操作需确认后继续 ✅
5. **后台不绕过 Waiting**: Heartbeat/Cron 跳过 WAITING_USER_INPUT ✅
6. **控制命令**: /approve/reject/retry/cancel/resume 正确执行 ✅
7. **状态守卫**: 完成任务不能被非法控制 ✅
8. **审计日志**: 所有控制动作可追溯 ✅

## Configuration

### 环境变量 (.env)

```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ALLOWED_CHAT_IDS=123456789
QIANFAN_API_KEY=your_key
```

### YAML 配置文件

位于 `config/` 目录：
- `app.yaml`: 应用设置
- `telegram.yaml`: Telegram bot 配置
- `llm.yaml`: LLM 提供商和模型
- `prompts.yaml`: 提示模板
- `tools.yaml`: 工具安全设置
- `memory.yaml`: 内存配置

## Project Structure

```
EgoCore/
├── app/
│   ├── main.py                 # 入口点
│   ├── telegram_bot.py         # Telegram 集成
│   ├── command_router.py       # 命令路由
│   ├── runtime/
│   │   ├── task_runtime.py     # 任务执行
│   │   ├── semantic_router.py  # 意图分类
│   │   ├── execution_result.py # 统一结果模型
│   │   ├── intent_mapper.py    # 意图映射 (P2-A.2)
│   │   ├── postcondition.py    # 后置条件验证 (P2-A.2)
│   │   ├── failure_policy.py   # 失败策略 (P2-B)
│   │   ├── heartbeat_driver.py # 心跳驱动 (P2-B)
│   │   ├── cron_driver.py      # 补偿驱动 (P2-B)
│   │   ├── guard.py            # 前后台隔离 (P2-B)
│   │   ├── approval_policy.py  # 确认策略 (P2-C)
│   │   ├── reply_binding.py    # 回复绑定 (P2-C)
│   │   ├── resume_driver.py    # 恢复驱动 (P2-C)
│   │   └── ...
│   ├── memory/                 # 内存系统
│   ├── tools/                  # 工具系统
│   ├── storage/                # 数据库层
│   └── logs/                   # 事件日志
├── config/                     # YAML 配置
├── data/                       # 运行时数据
│   └── shadow_metrics/         # Shadow 事件日志
├── docs/                       # 文档
│   └── runtime_metrics_aggregator/
│       └── SHADOW_THRESHOLDS.md
├── artifacts/                  # 阶段交付物
│   └── verification/           # 验收证据
│       └── runtime-metrics-shadow/  # Shadow 观察报告
│           ├── daily/          # 每日报告
│           └── summary_14day.md  # 14天汇总
├── tools/                      # 脚本工具
│   ├── shadow_metrics_daily_check.py  # 每日报告
│   └── shadow_metrics_summary.py      # 14天汇总
└── tests/                      # 测试套件
```

## 下一步方向

可选：
- P2-D: 性能优化
- P2-E: 增强调试能力

待定：
- Phase 3: 更复杂的多步骤工作流

**注意**: 多 Agent / Dashboard / 大型 DSL 不在当前规划内。

## License

MIT License
