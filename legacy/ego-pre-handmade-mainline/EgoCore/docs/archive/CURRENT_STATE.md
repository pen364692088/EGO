# EgoCore Current State

**Last Updated**: 2026-03-13
**Commit**: 271766f
**Phase**: P2-C Complete

## 阶段概览

| 阶段 | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| Phase 1 | 核心功能 | ✅ 完成 | 2026-03-13 |
| P2-A | 工具执行安全边界 | ✅ 完成 | 2026-03-13 |
| P2-A.1 | 主链接线收口 | ✅ 完成 | 2026-03-13 |
| P2-A.2 | 意图映射 + 后置条件验证 | ✅ 完成 | 2026-03-13 |
| P2-B | 后台推进最小闭环 | ✅ 完成 | 2026-03-13 |
| P2-C | Human-in-the-Loop (Ask/Wait/Resume) | ✅ 完成 | 2026-03-13 |

## 当前能力

### 已实现

1. **语义路由** - 5 种意图分类 (chat, question, new_task, continue, command)
2. **任务运行时** - 创建、规划、执行、暂停、恢复
3. **工具系统** - file, shell, python + preflight 安全检查
4. **内存系统** - 任务内存、checkpoint、恢复上下文
5. **意图映射** - 正确解析用户操作意图
6. **后置条件验证** - 验证执行结果是否达成目标
7. **失败策略** - failure_class → background_action 映射
8. **心跳驱动** - 30s 间隔任务推进
9. **补偿驱动** - 5min 间隔停滞任务恢复
10. **前后台隔离** - 会话、偏好、回复通道隔离
11. **通知策略** - 必须通知 vs 默认不通知
12. **状态查询** - 任务状态摘要
13. **确认策略 (P2-C)** - 高风险操作/多意图消歧需确认
14. **等待状态 (P2-C)** - WAITING_USER_INPUT 状态
15. **回复绑定 (P2-C)** - 用户回复绑定原任务
16. **恢复驱动 (P2-C)** - 确认后恢复执行

### 核心保护

**假成功防护**:
- `INTENT_MISMATCH`: 工具执行成功但操作错误 → 永不自动重试
- `POSTCONDITION_FAILED`: 工具执行成功但目标未达成 → 永不自动重试
- `PATH_EXTRACTION_ERROR`: 无法解析目标路径 → 永不自动重试

**Human-in-the-Loop 保护**:
- 高风险操作（delete/overwrite）需用户确认
- 多意图消歧需用户选择
- 后台不绕过 WAITING_USER_INPUT

## 当前边界

### 明确不做

- ❌ 多 Agent 编排
- ❌ Web Dashboard
- ❌ 大型 Workflow DSL
- ❌ 子代理编排系统

### 明确只做

- ✅ 单 Agent Runtime
- ✅ Telegram 驱动
- ✅ 最小后台推进闭环
- ✅ 假成功防护
- ✅ Human-in-the-Loop 最小闭环

## 测试状态

```
tests/test_p2c.py             - 29 tests ✅
tests/test_p2b.py             - 31 tests ✅
tests/test_p2_a2_intent.py    - 15 tests ✅
tests/test_semantic_router.py - 37 tests ✅
Total: 112 passed, 1 warning
```

## 关键文件

### 核心运行时

| 文件 | 职责 |
|------|------|
| `app/runtime/task_runtime.py` | 任务执行引擎 |
| `app/runtime/execution_result.py` | 统一结果模型 |
| `app/runtime/intent_mapper.py` | 意图映射 |
| `app/runtime/postcondition.py` | 后置条件验证 |
| `app/runtime/failure_policy.py` | 失败策略 |
| `app/runtime/heartbeat_driver.py` | 心跳驱动 |
| `app/runtime/cron_driver.py` | 补偿驱动 |
| `app/runtime/guard.py` | 前后台隔离 |
| `app/runtime/notification_policy.py` | 通知策略 |
| `app/runtime/status_query.py` | 状态查询 |
| `app/runtime/approval_policy.py` | 确认策略 (P2-C) |
| `app/runtime/reply_binding.py` | 回复绑定 (P2-C) |
| `app/runtime/resume_driver.py` | 恢复驱动 (P2-C) |
| `app/runtime/confirmation_renderer.py` | 确认消息渲染 (P2-C) |

### 验收文档

| 文件 | 职责 |
|------|------|
| `artifacts/verification/P2C_E2E_ASK_WAIT_RESUME.md` | Ask/Wait/Resume 闭环 |
| `artifacts/verification/P2C_REPLY_BINDING_REGRESSION.md` | 回复绑定回归 |
| `artifacts/verification/P2C_BACKGROUND_WAITING_GUARD.md` | 后台隔离验收 |
| `artifacts/verification/P2B_E2E_VERIFICATION.md` | 端到端验收 |
| `artifacts/verification/P2B_FALSE_SUCCESS_CONTAINMENT.md` | 假成功防护 |

## 下一步

可选：
- P2-D: 性能优化
- P2-E: 增强调试能力

待定：
- Phase 3: 更复杂的多步骤工作流
