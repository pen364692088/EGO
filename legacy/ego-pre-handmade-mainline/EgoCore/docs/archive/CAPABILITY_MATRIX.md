# EgoCore Capability Matrix

## 核心能力矩阵

| 能力 | Phase 1 | P2-A | P2-A.1 | P2-A.2 | P2-B | P2-C |
|------|---------|------|--------|--------|------|------|
| 语义路由 | ✅ | - | - | - | - | - |
| 任务创建/规划 | ✅ | - | - | - | - | - |
| 任务执行 | ✅ | ✅ | ✅ | ✅ | - | ✅ |
| 工具系统 | ✅ | ✅ | - | - | - | - |
| 内存持久化 | ✅ | - | - | - | - | - |
| Checkpoint | ✅ | - | - | - | - | ✅ |
| 作用域隔离 | ✅ | - | - | - | - | ✅ |
| Preflight 检查 | - | ✅ | - | - | - | - |
| Tool Doctor | - | ✅ | - | - | - | - |
| 主链接线收口 | - | - | ✅ | - | - | - |
| 意图映射 | - | - | - | ✅ | - | - |
| 后置条件验证 | - | - | - | ✅ | - | - |
| 失败策略 | - | - | - | - | ✅ | - |
| Heartbeat 驱动 | - | - | - | - | ✅ | - |
| Cron 补偿 | - | - | - | - | ✅ | - |
| 前后台隔离 | - | - | - | - | ✅ | ✅ |
| 通知策略 | - | - | - | - | ✅ | ✅ |
| 状态查询 | - | - | - | - | ✅ | ✅ |
| 确认策略 | - | - | - | - | - | ✅ |
| 等待状态 | - | - | - | - | - | ✅ |
| 回复绑定 | - | - | - | - | - | ✅ |
| 恢复驱动 | - | - | - | - | - | ✅ |

## 工具能力矩阵

| 工具 | 操作 | Phase 1 | P2-A | P2-A.2 |
|------|------|---------|------|--------|
| **file** | read | ✅ | ✅ | ✅ |
| | write | ✅ | ✅ | ✅ |
| | list | ✅ | ✅ | ✅ |
| | mkdir | ✅ | ✅ | ✅ |
| **shell** | execute | ✅ | ✅ | - |
| **python** | execute | ✅ | ✅ | - |

## 失败处理矩阵

| 失败类型 | 自动重试 | Heartbeat | Cron | 最终状态 |
|----------|----------|-----------|------|----------|
| INTENT_MISMATCH | ❌ | ❌ | ❌ | failed |
| POSTCONDITION_FAILED | ❌ | ❌ | ❌ | failed |
| PATH_EXTRACTION_ERROR | ❌ | ❌ | ❌ | failed |
| SAFETY_BLOCK | ❌ | ❌ | ❌ | blocked |
| PERMISSION_ERROR | ❌ | ❌ | ❌ | failed |
| TIMEOUT | ✅ (3) | ✅ | ✅ | failed |
| ENVIRONMENT_ERROR | ✅ (3) | ✅ | ✅ | failed |
| MODEL_ERROR | ✅ (3) | ✅ | ✅ | failed |
| TOOL_ERROR | ✅ (2) | ✅ | ✅ | failed |
| NOT_FOUND | ✅ (2) | ✅ | ✅ | failed |

## 通知矩阵

| 通知类型 | 前台 | 后台 |
|----------|------|------|
| TASK_COMPLETED | ✅ | ✅ |
| TASK_BLOCKED | ✅ | ✅ |
| MANUAL_ACTION_REQUIRED | ✅ | ✅ |
| INTENT_MISMATCH_BLOCKED | ✅ | ✅ |
| PATH_EXTRACTION_BLOCKED | ✅ | ✅ |
| STATUS_QUERY_RESPONSE | ✅ | ✅ |
| TASK_FAILED | ✅ | ✅ |
| HEARTBEAT_TICK | ✅ | ❌ |
| CRON_TICK | ✅ | ❌ |
| RETRY_ATTEMPT | ✅ | ❌ |
| CHECKPOINT_SAVE | ✅ | ❌ |

## 状态转换矩阵

| 从状态 | 可转换到 |
|--------|----------|
| created | planning, aborted |
| planning | running, paused, aborted |
| running | paused, blocked, **waiting_user_input**, completed, failed, aborted |
| paused | running, aborted |
| blocked | running, failed, aborted |
| **waiting_user_input** | **running**, failed, aborted |
| completed | (terminal) |
| failed | (terminal) |
| aborted | (terminal) |

## Human-in-the-Loop 矩阵 (P2-C)

| 确认类型 | 触发场景 | 用户回复 |
|----------|----------|----------|
| YES_NO | 高风险操作、覆盖确认 | yes/no/是/否 |
| OPTION_SELECT | 多候选目标 | 选项编号 |
| INTENT_DISAMBIGUATE | 多意图消歧 | 选项编号 |
| PATH_CLARIFY | 路径不明确 | 路径字符串 |
| FREE_TEXT | 需要补充信息 | 任意文本 |

## 边界矩阵

| 特性 | 支持 | 说明 |
|------|------|------|
| 单 Agent | ✅ | 当前只支持单 Agent |
| 多 Agent | ❌ | 不在规划内 |
| Telegram | ✅ | 主要驱动方式 |
| Dashboard | ❌ | 不在规划内 |
| Workflow DSL | ❌ | 不在规划内 |
| Heartbeat | ✅ | 30s 间隔 |
| Cron | ✅ | 5min 间隔 |
| 子代理编排 | ❌ | 不在规划内 |
| Human-in-the-Loop | ✅ | Ask/Wait/Resume |
| 自动确认 | ❌ | 不替用户做决定 |
