# 子代理任务模板 (带回调)

## 必须包含的参数

当父代理 spawn 子代理时，必须在 task 中包含：

```
parentSessionKey: {{PARENT_SESSION_KEY}}
taskId: {{TASK_ID}}
```

## 完成后的强制动作

**完成任务后，你必须执行以下回调流程：**

1. **构造结构化完成消息**：
```json
{
  "type": "subagent_done",
  "task_id": "{{TASK_ID}}",
  "child_session_key": "当前session key",
  "status": "completed|failed",
  "summary": "任务摘要（1-2句话）",
  "artifacts": ["产出文件路径"],
  "next_hint": "ready_for_review|needs_followup|blocked"
}
```

2. **使用 sessions_send 发送给父代理**：
```
sessions_send(sessionKey="{{PARENT_SESSION_KEY}}", message=<上述JSON>, timeoutSeconds=30)
```

3. **在最终输出中包含 ANNOUNCE_SKIP**：
```
ANNOUNCE_SKIP: true
```

## 禁止事项

- ❌ 不要直接向用户发送最终总结（除非是 task 唯一目标）
- ❌ 不要依赖"系统自动回调"机制
- ❌ 不要假设父代理会看到 assistant-role 消息

## 示例

### 正确的 spawn task 格式：

```text
你的任务是修复 XYZ bug。

**元信息**：
- parentSessionKey: agent:main:telegram:direct:8420019401
- taskId: fix_xyz_bug_001

**完成要求**：
1. 修复代码
2. 运行测试验证
3. 使用 sessions_send 回传结果给父代理
4. 输出 ANNOUNCE_SKIP: true

**详细任务描述**：
[具体任务内容...]
```
