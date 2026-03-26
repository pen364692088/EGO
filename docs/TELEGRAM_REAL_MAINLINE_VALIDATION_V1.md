# Telegram 真实主链验证 v1

> 正式验证体系文档
> 版本：v1.0
> 证据层级：E2-E4
> 状态：E4 样本级已验证，E5 准入通过，待执行观察期

---

## 一、定位与目标

### 定位

把 Telegram 真实渠道变成正式验收真相源。没有 `real_telegram` 证据，不允许宣称"已接主链/已启用/已生效"。

### 目标

建立三层证据分级验证体系：
- **simulated**: 脚本级验证（E2）
- **integration**: 多模块联调验证（E3）
- **real_telegram**: 真实渠道验证（E4）

### 成功判据

1. 能区分三类证据，报告中不再混用
2. 真实 Telegram 消息形成完整 tape
3. 至少一组真实成功样本 + 一组真实失败样本
4. 至少一组真实失败样本纳入回归
5. 最终汇报口径与证据层级匹配

---

## 二、证据分级定义

### E2 — simulated

**定义**: 单测、mock、模拟消息、离线脚本验证

**允许口径**:
- 模拟验证通过
- 脚本级通过
- 内部逻辑正确

**禁止口径**:
- 已接主链
- 已启用
- 已生效

### E3 — integration

**定义**: 多模块真实联调，但外部渠道是受控环境

**允许口径**:
- 集成验证通过
- 具备真实主链验证条件
- 主链候选可用

**禁止口径**:
- 正式生效
- 稳定运行
- 已接主链

### E4 — real_telegram

**定义**: 真实 Telegram 渠道、真实入站/出站、完整 tape

**允许口径**:
- 已接入真实主链
- 已启用
- 样本级生效

**禁止口径**:
- 关键未知为无
- 稳定收口
- 观察期完成

---

## 三、Tape Recorder 规范

每条真实 Telegram 验证必须形成完整 tape：

```yaml
tape:
  update_id: int
  timestamp: ISO8601

  # 入站
  raw_update: dict              # 原始 Telegram update
  normalized_event: dict        # 归一化事件

  # 处理
  openemotion_input: dict       # 结构化输入
  openemotion_output: dict      # 结构化输出

  # 裁决
  response_plan: dict           # EgoCore 响应计划
  safety_decision: dict         # 安全裁决

  # 出站
  outbound_action: dict         # 实际发送的消息/动作
  delivery_status: str          # 交付状态

  # 审计
  trace_id: str
  replay_hash: str
  artifact_paths: list
```

---

## 四、失败样本规范

每个失败样本必须包含：

| 字段 | 说明 |
|------|------|
| failure_id | 唯一标识 |
| timestamp | 触发时间 |
| raw_input | 原始输入 |
| expected | 预期行为 |
| actual | 实际行为 |
| evidence_level | E2/E3/E4 |
| tape_path | 相关 tape 文件 |
| preliminary_cause | 初步归因 |
| in_regression | 是否纳入回归 |
| retested | 修复后是否复测 |

---

## 五、脚本入口

| 脚本 | 层级 | 用途 |
|------|------|------|
| `scripts/run_telegram_simulated_smoke.py` | E2 | 模拟验证 |
| `scripts/run_telegram_integration_e2e.py` | E3 | 集成验证 |
| `scripts/run_telegram_real_channel_capture.py` | E4 | 真实渠道捕获 |
| `scripts/start_egocore_telegram_windows.ps1` | - | Windows 环境启动真实 Telegram bot 采样 |
| `scripts/replay_real_failure_cases.py` | - | 失败样本回归 |

### 统一 runner 约束

- `simulated / integration / real_telegram` 必须共用同一条 `RuntimeV2Loop` 主链
- 差异只允许出现在：
  - 输入 source
  - 输出 transport
  - evidence_collector / source_type
- 不能因为环境差异把 E2/E3 改成旁路脚本；若 Linux 侧依赖不完整，可用当前机器的 Windows Python 执行，例如：

```bat
cmd.exe /c py -3 scripts\run_telegram_simulated_smoke.py --quick
cmd.exe /c py -3 scripts\run_telegram_integration_e2e.py --quick
```

- 统一 runner 的跨层一致性结论单独沉淀到 `artifacts/telegram_real_mainline_v1/reports/UNIFIED_RUNNER_CONSISTENCY_REPORT.md`

---

## 六、Artifacts 结构

```
artifacts/telegram_real_mainline_v1/
├── simulated/           # E2 证据
│   ├── smoke_*.json
│   └── reports/
├── integration/         # E3 证据
│   ├── tape_*.json
│   └── reports/
├── real_telegram/       # E4 证据
│   ├── update_*.json
│   ├── tape_*.json
│   └── reports/
├── failure_cases/       # 失败样本库
│   ├── failure_*.json
│   └── index.json
├── replays/             # 回放记录
│   └── replay_*.json
└── reports/
    └── VALIDATION_REPORT_V1.md
```

---

## 七、验收 Gate

### Gate A: Evidence Contract

- 每条证据已分级
- 结论与证据等级一致
- 无 simulated 冒充 real_telegram

### Gate B: Real Channel E2E

- 真实 Telegram update 已捕获
- 已形成 normalized event
- OpenEmotion 返回结构化结果
- EgoCore 做了最终裁决
- 实际出站消息可追踪
- tape/timeline/replay 完整

### Gate C: Failure Regression Integrity

- 至少 1 个真实失败样本被沉淀
- 至少 1 次修复后回放真实失败样本
- 报告无越级口径

---

## 八、严禁事项

1. 把 simulated 报告写成"已接主链/已启用/已生效"
2. 只给成功样本，不给真实失败样本
3. 没有原始 Telegram update 就声称 real_telegram 通过
4. 用人工主观聊天体验代替 artifacts
5. 把 OpenEmotion 自然语言解释当作程序消费字段
6. 没有 E5 证据时写"关键未知为无/已完全收口/稳定运行"
7. 把问题默认归到 OpenEmotion，不先排查 EgoCore

---

*此文档遵循 EGO 验收证据分级协议 v1*
