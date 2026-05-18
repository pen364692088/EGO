# EgoCore Changelog - Phases

## P0-R3: runtime 主链接线修复 (2026-03-25)

### 修复
- `EgoCore/app/runtime_v2/loop.py` - 新增 `_assess_risk_level()` 风险评估函数
- `EgoCore/app/runtime_v2/loop.py` - 修复 `proto_self_event.safety_context` 不再硬编码为空
- `EgoCore/app/runtime_v2/loop.py` - 添加 `risk` 和 `risk_level` 双字段传递

### 核心成果
- ✅ `runtime_v2/loop.py` 正确评估风险并传递到 `safety_context`
- ✅ 高风险操作的 psi_bucket 包含 `:risk_high` 后缀
- ✅ 高低风险操作被分配到不同 cycle
- ✅ 真实 Telegram 环境验证通过

### 验证数据
| 消息 | psi_bucket | cycle_id | risk_signal |
|------|------------|----------|-------------|
| 删除临时文件 | `telegram:user_message:file_risk_op:risk_high` | `f7c8318dccc2d7c0` | 0.5 |
| 读取文件 test.txt | `telegram:user_message:test_verify` | `34c1264506f1d7fe` | 0.1 |

### 测试
- `EgoCore/scripts/p0_r3_unit_test.py` - 单元测试 (13/13 通过)
- `EgoCore/scripts/p0_r3_e2e_test.py` - E2E 测试 (全部通过)

### 报告
- `Tasks/p0_steady_state/reports_r3/P0_R3_REPORT.md`

---

## P0-FINAL: 真实 Telegram 双样本现场核验 (2026-03-25)

### 验证状态
- ✅ 高风险 bucket 含 `:risk_high`
- ✅ 低风险 bucket 不含 `:risk_high`
- ✅ 两者 cycle_id 不同
- ✅ 真实 Telegram 环境验证通过

### 报告
- `Tasks/p0_steady_state/reports_final/P0_FINAL_VERIFICATION_REPORT.md`

---

## P0-R2: Risk Signal 接线 (2026-03-25)

### 修复
- `EgoCore/app/openemotion_adapter/event_builder.py` - 添加 `risk` 字段映射
- `OpenEmotion/openemotion/proto_self/appraisal.py` - 修复 `_score_identity_conflict` 类型 bug
- `OpenEmotion/openemotion/proto_self/appraisal.py` - 修复 `_score_risk` 类型 bug

### 核心成果
- ✅ `safety_context.risk` 正确从 EgoCore 传递到 OpenEmotion
- ✅ 高风险操作 psi_bucket 包含 `:risk_high` 后缀
- ✅ 高低风险操作被分配到不同 cycle

---

## P0-R1: 真实 Telegram 验证 (2026-03-25)

### 验证
- EgoCore 服务在真实 Telegram 环境正常运行
- Cycle 聚合机制工作正常（hits 递增, strength 累积）
- Reflection 机制工作正常（revision_counter 增加）
- 诊断脚本输出与真实状态一致

### 报告
- `Tasks/p0_steady_state/reports_r1/` - 5 份 R1 报告

---

## P0: 高风险误聚合修复 (2026-03-25)

### 修复
- `OpenEmotion/openemotion/proto_self/cycles.py` - psi_bucket 追加 risk_level
- `OpenEmotion/openemotion/proto_self/appraisal.py` - safety_context 传递

### 核心成果
- HIGH 风险操作与低风险操作被区分
- 关键词优先级冲突修复
- N2 成立条件未被破坏

### 测试
- `OpenEmotion/scripts/p0_regression_test.py` - 5/5 回归测试通过

---

## P2-C: Human-in-the-Loop 最小闭环 (2026-03-13)

### 新增

- `app/runtime/approval_policy.py` - 确认策略
- `app/runtime/confirmation_renderer.py` - 确认消息渲染
- `app/runtime/reply_binding.py` - 回复绑定
- `app/runtime/resume_driver.py` - 恢复驱动

### 核心特性

1. **确认策略**:
   - 高风险操作检测（delete/overwrite）
   - 多意图消歧
   - 多候选目标选择
   - 路径澄清

2. **等待状态**:
   - TaskStatus.WAITING_USER_INPUT
   - waiting_reason / waiting_request / user_decision 字段
   - 状态机支持

3. **确认消息渲染**:
   - YES_NO 简单确认
   - OPTION_SELECT 多选
   - PATH_CLARIFY 路径澄清
   - Telegram 格式化

4. **回复绑定**:
   - 绑定到最近 waiting task
   - Scope/Session 一致性检查
   - 防误绑普通聊天

5. **恢复驱动**:
   - 不新建平行任务
   - 恢复原任务继续执行
   - 走统一执行主链

6. **后台隔离**:
   - Heartbeat 跳过 WAITING_USER_INPUT
   - Cron 跳过 WAITING_USER_INPUT

### 测试

- `tests/test_p2c.py` - 29 tests
- 总计: 112 passed

---

## P2-B: 后台推进最小闭环 (2026-03-13)

### 新增

- `app/runtime/failure_policy.py` - 失败类型 → 后台动作映射
- `app/runtime/heartbeat_driver.py` - 30s 心跳驱动
- `app/runtime/cron_driver.py` - 5min 补偿驱动
- `app/runtime/guard.py` - 前后台隔离保护
- `app/runtime/notification_policy.py` - 通知策略
- `app/runtime/status_query.py` - 状态查询

### 核心特性

1. **失败策略**: 
   - INTENT_MISMATCH / POSTCONDITION_FAILED / PATH_EXTRACTION_ERROR 永不自动重试
   - TIMEOUT / ENVIRONMENT_ERROR / MODEL_ERROR 可重试

2. **心跳驱动**:
   - 30s 扫描可推进任务
   - Lease 防止并发执行
   - 严格遵循失败策略

3. **补偿驱动**:
   - 5min 扫描停滞任务
   - 对允许恢复的任务做一次安全推进
   - 永不对假成功失败重试

4. **前后台隔离**:
   - 后台不接管前台会话
   - 后台不改写前台偏好
   - 回复通道隔离

5. **通知策略**:
   - 必须通知: completed, blocked, manual_action_required
   - 默认不通知: heartbeat_tick, cron_tick, retry_attempt

### 测试

- `tests/test_p2b.py` - 31 tests
- 累计: 83 passed

---

## P2-A.2: 意图映射 + 后置条件验证 (2026-03-13)

### 新增

- `app/runtime/intent_mapper.py` - 操作意图解析
- `app/runtime/postcondition.py` - 后置条件验证

### 核心特性

1. **意图映射**:
   - 从用户消息中提取操作意图
   - 识别 LIST_DIR, READ_FILE, WRITE_FILE, MKDIR, EXISTS 操作
   - 提取目标路径

2. **后置条件验证**:
   - 验证工具执行结果是否达成用户目标
   - LIST_DIR 验证目录存在
   - READ_FILE 验证文件存在且可读
   - WRITE_FILE 验证文件创建成功

### 测试

- `tests/test_p2_a2_intent.py` - 15 tests

---

## P2-A.1: 主链接线收口 (2026-03-13)

### 核心特性

1. **统一执行结果模型**:
   - `UnifiedExecutionResult` 包含 status, failure_class, retry_hint, evidence
   - 所有执行路径返回相同类型

2. **主链真正收口**:
   - 所有工具执行通过 `execute_next_step_unified()`
   - 统一的失败分类和重试提示

---

## P2-A: 工具执行安全边界 (2026-03-13)

### 新增

- `app/runtime/tool_doctor.py` - 工具健康诊断
- `app/tools/` 增强 - preflight 检查

### 核心特性

1. **Preflight 检查**:
   - 工具执行前安全检查
   - 危险命令拦截
   - 路径安全验证

2. **Tool Doctor**:
   - 工具健康诊断
   - 依赖检查
   - 权限验证

---

## Phase 1: 核心功能 (2026-03-13)

### 新增

- `app/main.py` - 入口点
- `app/telegram_bot.py` - Telegram 集成
- `app/command_router.py` - 命令路由
- `app/runtime/task_runtime.py` - 任务执行
- `app/runtime/semantic_router.py` - 意图分类
- `app/runtime/state_machine.py` - 状态机
- `app/runtime/checkpoint.py` - Checkpoint
- `app/runtime/planner.py` - 任务规划
- `app/memory/` - 内存系统
- `app/tools/` - 工具系统
- `app/storage/` - 数据库层
- `app/logs/` - 事件日志
- `config/` - YAML 配置

### 核心特性

1. **语义路由**:
   - 5 种意图分类: chat, question, new_task, continue, command
   - 自然语言任务创建

2. **任务运行时**:
   - 任务创建、规划、执行
   - 暂停、恢复支持
   - 作用域隔离

3. **工具系统**:
   - file: 读/写/列文件
   - shell: 执行命令
   - python: 运行代码

4. **内存系统**:
   - 任务内存连续性
   - Checkpoint 持久化
   - 恢复上下文构建

### 测试

- `tests/test_semantic_router.py` - 37 tests
