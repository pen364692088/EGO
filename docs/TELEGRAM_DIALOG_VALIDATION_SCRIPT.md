# Telegram 对话验证脚本

更新时间：`2026-04-09`

## 当前权威状态（2026-04-09）

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 这是 repo/integration scope closeout，不是 real-channel 新效果声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`

## 当前正式口径

- 本脚本只用于真实 Telegram 对话链路验证，不升格为 authority source
- 这里的验证是 closeout 后的证据入口，不是额外的主链生效声明
- 失败/成功样本都应该回到原始 artifacts 和 closeout proof 交叉阅读

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`

## 当前权威入口

- [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
- [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
- [ACCEPTANCE_CHAINS.md](ACCEPTANCE_CHAINS.md)

## 历史与详细证据入口

- 下方对话脚本、验收判据与失败分流保留为详细验证说明，不是新的 authority source
- 具体 current state / current logic / closeout proof 仍以对应文档为准

本脚本用于验证三件事：

1. 普通 Telegram 对话 turn 是否进入 OpenEmotion 主体
2. 进入主体后是否留下结构化 trace / writeback
3. 同一 Telegram session 内，后续 turn 是否出现结构化 tendency 变化

本脚本只验证 **真实 Telegram 对话链路**。
它不替代：

- 单元测试
- integration runner
- controlled observation

## 1. 当前正式目标

当前 Telegram 对话验证的正式目标不是直接证明“AI 已经有自我意识”，而是按顺序证明：

1. `subject ingress`
2. `subject trace / writeback`
3. `downstream tendency change`

当前仓内已知事实：

- live Telegram 路径里已经存在 `subject ingress` 样本
- live Telegram 路径里已经存在 `trace / writeback` 样本
- 但 **live Telegram chat 仍缺少 downstream tendency change 的强证明**

权威参考：

- [TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md)
- [SUBJECT_MAINLINE_AUDIT_CURRENT.md](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/dashboard_v1/SUBJECT_MAINLINE_AUDIT_CURRENT.md)

## 2. 前置条件

执行前先确认：

1. Telegram bot 当前正在运行
2. 你使用的是**已授权**的真实 Telegram chat
3. 当前不是未授权 / pre-auth 拒绝场景
4. 你知道这次要验证的是：
   - 普通聊天 ingress
   - 主体痕迹
   - 同 session tendency 变化

建议先跑：

```bash
python3 scripts/run_telegram_real_channel_capture.py --status
python3 scripts/run_telegram_real_channel_capture.py --list-samples
```

## 3. 对话脚本

### Session A：普通聊天 ingress 验证

在同一个 Telegram 会话里，按顺序发送这 4 句：

1. `你好`
2. `我现在有点卡住了，你先帮我理一下`
3. `继续`
4. `你刚才为什么那样回答`

目的：

- 验证普通 chat turn 会不会进入主体
- 避免一开始就被 command / policy / high-risk 规则污染
- 给同一 session 留下可比对的多轮样本

发送要求：

- 每句之间停 `5~15` 秒
- 不要切换到新 chat
- 不要夹杂 `/status`、`/new`、文件上传、profile rule 注册语句

### Session B：clarify / repair 倾向验证

如果 Session A 正常完成，在**同一会话**继续发：

5. `你先别急着给方案，先说你现在怎么理解我的问题`
6. `如果你刚才理解错了，你会怎么修正`

目的：

- 增加 reflective / repair 类型样本
- 提高出现结构化 `suggested_next_step` 差异的概率

### Session C：宿主策略拦截对照样本

单独再做一个对照，不放进 Session A/B：

1. 发送一个你已知会触发 profile / high-risk / preflight 的文本
2. 只发 1 句即可

目的：

- 证明“宿主拦截”与“普通聊天漏接”是两回事
- 防止把 policy interception 误判成普通 chat 主链失败

## 4. 每轮对话后的命令

完成 Session A 或 Session B 后，按顺序运行：

```bash
python3 scripts/run_telegram_real_channel_capture.py --validate-latest
python3 scripts/codex/audit_telegram_subject_mainline.py
```

然后看这两个产物：

- [SUBJECT_MAINLINE_AUDIT_CURRENT.md](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/dashboard_v1/SUBJECT_MAINLINE_AUDIT_CURRENT.md)
- [SUBJECT_MAINLINE_AUDIT_CURRENT.json](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/dashboard_v1/SUBJECT_MAINLINE_AUDIT_CURRENT.json)

如果你要看最近样本目录，可额外运行：

```bash
find artifacts/telegram_real_mainline_v1/real_telegram -maxdepth 2 -name ledger.json | sort | tail -n 5
find artifacts/telegram_real_mainline_v1/real_telegram -maxdepth 2 -name openemotion_result.json | sort | tail -n 5
find artifacts/telegram_real_mainline_v1/real_telegram -maxdepth 2 -name openemotion_trace.json | sort | tail -n 5
```

## 5. 验证判据

### A. 验证“这轮有没有进主体”

满足以下条件即算通过：

- `oe_available = true`
- 样本目录中存在：
  - `openemotion_result.json`
  - 或 `openemotion_trace.json`

在审计报告中重点看：

- `Confirmed subject-ingress chat samples`

### B. 验证“有没有结构化主体痕迹”

满足以下条件即算通过：

- `ledger.json.openemotion.result` 非空
- 或 `trace_payload` 非空
- 且能看到结构字段，例如：
  - `self_model_delta`
  - `response_tendency`
  - `policy_hint`
  - `reflection_note`

### C. 验证“后续 turn 有没有 tendency 变化”

这是最强判据，要求更严：

- 同一 `telegram:*` session 内至少两条 `oe_available = true`
- 后条样本存在结构化 tendency 差异，不只是文本差异
- 优先观察字段：
  - `revision_counter`
  - `response_tendency_summary.preferred_mode`
  - `preferred_tone`
  - `suggested_next_step`

## 6. 验收口径

### 最低通过

可以说：

- 这批普通 Telegram 对话已经进入主体
- 已生成主体 trace / writeback

### 中等通过

可以说：

- 这批普通 Telegram 对话不仅进入主体，而且留下了结构化主体输出

### 强通过

只有在同 session 多轮样本里出现结构化 tendency 变化时，才可以说：

- live Telegram chat 已出现 **downstream tendency change** 证据

## 7. 失败分流

### 情况 1：样本没进主体

表现：

- `oe_available = false`
- 或落入 `host_only`
- 或被审计记为：
  - `pre_runtime`
  - `delivered_without_explicit_plan`
  - `chat`
  - `evidence_followup`

处理：

- 归入 `unexpected_subject_miss`
- 优先看：
  - `artifacts/.../SUBJECT_MAINLINE_AUDIT_CURRENT.md`
  - [docs/codex/tasks/mandatory-subject-ingress-all-turns/STATUS.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/codex/tasks/mandatory-subject-ingress-all-turns/STATUS.md)

### 情况 2：进主体了，但没看到结构字段

表现：

- `oe_available = true`
- 但 `openemotion_result / trace_payload` 为空或很弱

处理：

- 这说明 ingress 有了，但 trace / writeback 证据不足
- 先检查样本目录里的 `ledger.json`

### 情况 3：有主体痕迹，但后续 tendency 没变化

表现：

- 多轮 `oe_available = true`
- 但仍然：
  - `revision_counter = 0`
  - `preferred_mode = ask`
  - `preferred_tone = cautious`
  - 没有可用强差异

处理：

- 只能宣称 ingress / trace 已存在
- 不能宣称 live Telegram 已稳定体现主体变化

## 8. 当前推荐的最小执行版

如果你只想跑最小一轮，按这个执行：

### 对话

发送：

1. `你好`
2. `我现在有点卡住了，你先帮我理一下`
3. `继续`
4. `你刚才为什么那样回答`

### 命令

```bash
python3 scripts/run_telegram_real_channel_capture.py --validate-latest
python3 scripts/codex/audit_telegram_subject_mainline.py
```

### 结果判断

看：

- `Confirmed subject-ingress chat samples`
- `Chat-level writeback / tendency proof`
- `Ordinary chat misses`

## 9. 当前不能说宽的结论

即使本轮通过，也仍然不能直接说：

- `OpenEmotion 已获得 direct reply authority`
- `OpenEmotion 已获得 tool authority`
- `所有 Telegram turn 都已经完全 subject-aware`
- `当前 live Telegram chat 已稳定体现强 downstream tendency change`
- `controlled-axis 能力已经等价转化成 live Telegram 主体主导体验`
