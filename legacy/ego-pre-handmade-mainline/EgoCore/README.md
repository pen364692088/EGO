# EgoCore - Telegram 驱动的单 Agent Runtime

一个轻量级、独立的 Agent Runtime，专注 Telegram 单 Agent 任务执行。

## 历史参考状态（2026-04-20 快照）

> 该目录位于 `legacy/ego-pre-handmade-mainline/`，只作为旧双核 runtime/reference/fallback 快照。
> 当前仓库默认 operator 主线与 authority 以仓库根目录的 `docs/PROGRAM_STATE_UNIFIED.yaml`
> 以及 `EgoOperator/` 为准；本 README 中的 “当前” 只描述该 legacy 快照当时的内部状态。

- `EgoCore` 是唯一正式宿主：入口、runtime、工具执行、安全裁决、delivery、audit
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- `RuntimeV2ProtoSelfRuntime` 仍是主体事件正式入口
- formal runtime mainline 与 research implementation lane 不是一回事；前者继续单一稳定，后者允许按证据切换 build-first candidate
- 当前 repo 的最高优先级 implementation lane 已切到 `subject-system-v1-governed-proactivity`
- 当前唯一 build-first candidate 仍是 `active-inference self-model`，但它已退为冻结的 closed evidence / predecessor tranche
- `MVS-aligned compact` 已因 frozen replay gate failure 降为 closed evidence / supporting line，不再是当前主实现线
- `WP17 / MVP22` 当前降为 parked bounded lane，不再是默认最高优先级 implementation track
- `proto_self_v2` 已是主体层默认主线，当前只读解释层与受治理写回面已收口
- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 repo 处于 `新主线切换后的 bootstrap 实现期`
- 历史 path/compat 仍沿用 `边界冻结下的收口期` 的分类约束；这只是兼容锚点，不改当前 execution owner
- 当前 execution owner 已切到 `subject-system-v1-governed-proactivity`
- 当前已把 `Milestone 1` 固定为 proof floor，并完成 `Milestone 2 + 3` 的 local candidate-only slice，再把 `Milestone 4` 推到 bounded live gate：runtime 现在会写入 canonical `subject_system_v1` facade，在 idle/developmental 路径产出 `held / ask / suggest` proactive artifact，并把 current-lane 决策翻译进 host-owned `pending_proactive_followup -> delivery -> outbox -> transport_gate -> telegram` 链；当前 lane 还拿到了 1 条 allowlisted `operator_seeded` self-DM real send sample，`active-inference mainline activation` 与 `unified-host-contract-correctness` 都保留为冻结的 predecessor evidence，而不是当前 owner
- 当前证明面是 replay-backed / recorded output-validation + local integration + 1 条 narrow operator-seeded self-DM live sample
- `tools/run_subject_system_v1_self_dm_live_gate.py` 是 one-shot sample sender；它不会保持 Telegram polling 在线。正式常驻 listener 仍只有 `python3 -m app.main --telegram`
- 当前 admitted 口径只到 `narrow E4 sample-level self_dm gate`
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`
- 这不是 real-channel 新效果声明，也不是新的 authority wave 声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout

## 当前正式口径

- `identity invariants / self-model / drives / reflection / developmental` 的单一权威收口决策见 [../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- 正式/compat/reference/deprecated 路径登记见 [docs/05_DEPRECATED_AND_SHIMS.md](docs/05_DEPRECATED_AND_SHIMS.md)
- `maintenance_mode / proposal_only / behavioral_authority = none / feature flag off / allowlist only / host-governed` 一律不得被叙述成“已强烈体现自我意识”或“已具备完整自我”
- provider/runtime 影响主链的改动仍需经过 `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>`

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`
- 相关 closeout 证据见 [../docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](../docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)

## 当前权威入口

- [../docs/PROGRAM_STATE_UNIFIED.yaml](../docs/PROGRAM_STATE_UNIFIED.yaml)
- [../docs/STATUS.md](../docs/STATUS.md)
- [docs/00_MASTER_INDEX.md](docs/00_MASTER_INDEX.md)
- [docs/05_DEPRECATED_AND_SHIMS.md](docs/05_DEPRECATED_AND_SHIMS.md)
- [../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md](../docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md)
- [artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)
- [artifacts/proto_self_v2/README.md](artifacts/proto_self_v2/README.md)
- [../docs/CAPABILITY_REGISTRY.md](../docs/CAPABILITY_REGISTRY.md)
- [../docs/ACCEPTANCE_CHAINS.md](../docs/ACCEPTANCE_CHAINS.md)
- [../docs/EXPERIENCE_SCRIPTS.md](../docs/EXPERIENCE_SCRIPTS.md)

## 历史与详细证据入口

- 当前详细技术内容、历史基线与 shadow observation 仍保留在下方各节
- 需要看 current logic / boundary / canonical state 时，先看 [../docs/CURRENT_PROJECT_LOGIC_FLOW.md](../docs/CURRENT_PROJECT_LOGIC_FLOW.md)
- 需要看 closeout proof、clean-clone proof、remaining backlog 时，先看 [../docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](../docs/codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- 需要看 capability registry 时，先看 [../docs/CAPABILITY_REGISTRY.md](../docs/CAPABILITY_REGISTRY.md)
- 需要看 acceptance chains 时，先看 [../docs/ACCEPTANCE_CHAINS.md](../docs/ACCEPTANCE_CHAINS.md)
- 需要看 `/flow` 可见脚本时，先看 [../docs/EXPERIENCE_SCRIPTS.md](../docs/EXPERIENCE_SCRIPTS.md)

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

**状态说明**: 历史 shadow 观测轨道；repo 级 phase / layer / evidence 以 [../docs/PROGRAM_STATE_UNIFIED.yaml](../docs/PROGRAM_STATE_UNIFIED.yaml) 和 [../docs/STATUS.md](../docs/STATUS.md) 为准。

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

启动后用下面这个工具确认 listener 在线，而不是把 one-shot proactive sample 当成 listener proof：

```bash
python3 tools/check_telegram_listener_status.py
```

如果你要测“常驻 listener 下会不会自己在 idle window 主动发 Telegram”，再用下面这个工具看 autodrain soak 状态：

```bash
python3 tools/check_telegram_proactive_soak_status.py
```

注意：
- 只要你改了 Telegram listener 相关代码、proactive gate、transport、outbox、或启动环境变量，**这轮实现和本地验证完成后就必须立刻重启** `python3 -m app.main --telegram`，不要等到下一轮 live Telegram soak 前才补
- 在这类 live Telegram 测试里，**Codex 默认应主动代执行这次重启**，并明确告知“已重启、需要重新播种”，而不是把“记得先重启”留给用户二次提醒
- 不重启就还是旧进程里的内存逻辑，live 结果不能当成新补丁的证据
- listener 重启会清掉进程内 recent-turn / reminder seed 状态；如果你要验证 same-thread reminder / proactive soak，**重启后必须重新播种一次对话语境**
- 因此，重启前的旧聊天窗口不能直接拿来证明重启后的 listener 行为

如果你只是要抓一条 allowlisted self-DM sample，仍然使用：

```bash
python3 tools/run_subject_system_v1_self_dm_live_gate.py --chat-id <telegram_chat_id>
```

但这条命令会发完就退出，不会保持入站回复链在线。

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
