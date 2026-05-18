# P1.5 Closure Summary

## 执行摘要

**状态**: P1.5-A 完成，P1.5-B/C 进行中

**跨 scope 误绑定风险**: ❌ 已消除

---

## 为什么 P1 不能直接宣称闭环

P1 完成了语义入口、自动首步执行、continue 基本体验，但存在三个主链缺口：

1. **任务作用域未隔离**
   - `get_active_task()` 是全局查询
   - 不同 chat/user 可能绑定到同一任务
   - 存在隐私和安全风险

2. **continue 与 `/resume` 使用不同 resolver**
   - continue: 全局 `list_tasks()` 倒查
   - resume: 只看 `PAUSED` 状态
   - 行为不一致，用户体验混乱

3. **Task Memory 未接主链**
   - memory 模块存在但未被调用
   - 任务连续性仅依赖 checkpoint
   - 恢复时缺少上下文

---

## 本次收口修了哪三条主链

### 1. 任务作用域隔离

**修改内容**:
- Task 模型添加 `chat_id`, `user_id`, `scope_key` 字段
- 数据库添加对应列（带迁移）
- Repository 添加 scoped 查询方法
- 所有命令处理器使用 scoped resolver

**关键代码**:
```python
# Task 创建时注入 scope
task = Task.create(objective, chat_id=chat_id, user_id=user_id, scope_key=scope_key)

# 查询时按 scope 过滤
task = repo.get_active_for_scope(scope_key)
```

### 2. 统一 Resolver

**修改内容**:
- 新增 `UnifiedTaskResolver` 类
- 实现 `resolve_task_for_continue()`, `resolve_task_for_resume()`, `resolve_task_for_run()`
- 所有入口点使用同一 resolver

**解析优先级**:
1. 显式 task_id
2. 当前 scope 下 active task
3. 当前 scope 下 resumable task
4. 当前 scope 下最近未完成任务
5. 无任务

### 3. Task Memory 接入

**修改内容**:
- 待完成（P1.5-B）

---

## 现在还剩什么边界未做

### P1.5-B
- T4: task memory 真接入
- T5: 统一恢复顺序

### P1.5-C
- T6: 状态类聊天接入 scope
- T7: 旧数据兼容策略
- T8: 诊断与文档

### P2 内容
- 多 Agent 编排
- heartbeat/cron 自动恢复
- Web UI/Dashboard
- 复杂 workflow DSL
