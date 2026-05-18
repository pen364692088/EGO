# Telegram E2E 测试入口使用说明

> **版本**: v1.0
> **日期**: 2026-03-24
> **适用**: EgoCore + Proto-Self Kernel v1

---

## 两层测试入口概览

| 入口 | 脚本路径 | 用途 | 依赖 |
|------|----------|------|------|
| **本地模拟** | `scripts/telegram_sim_harness.py` | 本地快速测试，不依赖 Telegram 网络 | 仅需 EgoCore 运行 |
| **真实 Bot API** | `scripts/telegram_bot_api_e2e.py` | 真实 Telegram E2E 测试 | 需要 Bot Token + Chat ID |

---

## 1. 本地模拟入口 (telegram_sim_harness)

### 用途
- 快速验证 Runtime 主链逻辑
- 无需 Telegram 网络连接
- 适合 CI/CD 集成

### 基本用法

```bash
# 单条消息测试
python scripts/telegram_sim_harness.py --message "读取文件 /tmp/test.txt"

# 验证 Proto-Self cycle
python scripts/telegram_sim_harness.py --message "读取文件 /tmp/test.txt" --verify-cycle

# 交互模式
python scripts/telegram_sim_harness.py --interactive

# 运行场景文件
python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/file_read_success.json

# 指定 session ID
python scripts/telegram_sim_harness.py --message "状态查询" --session my_test_session
```

### 输出

```
[INIT] Simulator initialized
[INIT] Session ID: sim_20260324_143022_a1b2c3d4
[INIT] Proto-Self enabled: True

[INPUT] 读取文件 /tmp/test.txt
[REPLY] 文件内容：Hello World
[STATUS] success

============================================================
Telegram Simulator Test Summary
============================================================
Session ID: sim_20260324_143022_a1b2c3d4
Total Tests: 1
Passed: 1
Failed: 0
Pass Rate: 100.0%
Trace File: logs/telegram_sim_trace.jsonl
State Mirror: artifacts/proto_self_mirror/state.json
============================================================
```

### Artifact 路径

| Artifact | 路径 |
|----------|------|
| Trace | `logs/telegram_sim_trace.jsonl` |
| State Mirror | `artifacts/proto_self_mirror/state.json` |

---

## 2. 真实 Bot API E2E 入口 (telegram_bot_api_e2e)

### 用途
- 真实 Telegram 端到端测试
- 验证完整网络链路
- 生产环境验证

### 前置要求

1. **Bot Token**: 从 @BotFather 获取
2. **Chat ID**: 你的 Telegram 用户 ID 或群组 ID

```bash
# 获取 Chat ID 方法：给 Bot 发一条消息，然后访问
# https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
# 从响应中提取 chat.id
```

### 基本用法

```bash
# 单条消息测试
python scripts/telegram_bot_api_e2e.py \
    --token "YOUR_BOT_TOKEN" \
    --chat-id 123456789 \
    --message "读取文件 /tmp/test.txt"

# 使用环境变量
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="123456789"
python scripts/telegram_bot_api_e2e.py --message "状态查询"

# 验证 Proto-Self cycle
python scripts/telegram_bot_api_e2e.py --message "读取文件" --verify-cycle

# 运行测试套件
python scripts/telegram_bot_api_e2e.py --suite file_read
python scripts/telegram_bot_api_e2e.py --suite external_failure
python scripts/telegram_bot_api_e2e.py --suite cycle_strengthen
python scripts/telegram_bot_api_e2e.py --suite smoke
```

### 可用测试套件

| 套件 | 命令 | 说明 |
|------|------|------|
| file_read | `--suite file_read` | 文件读取成功场景 |
| external_failure | `--suite external_failure` | 外部失败 reflection |
| cycle_strengthen | `--suite cycle_strengthen` | 发送3条相似消息验证 strengthen |
| smoke | `--suite smoke` | 基础冒烟测试 |

### 输出示例

```
[TEST] [E2E] 读取文件 /tmp/e2e_test_hello.txt
[SENT] message_id=1234
[REPLY] 文件内容：Hello from E2E test
[STATUS] success

============================================================
Telegram Bot API E2E Test Summary
============================================================
Session ID: e2e_20260324_143022_a1b2c3
Chat ID: 8420019401
Total Tests: 1
Passed: 1
Failed: 0
Pass Rate: 100.0%
Total Time: 3.45s
============================================================
```

---

## 3. 测试场景文件

### 场景文件格式 (JSON)

```json
{
  "name": "场景名称",
  "description": "场景描述",
  "session_id": "可选的 session ID",
  "messages": [
    {
      "text": "消息内容",
      "expected_contains": "期望回复中包含的文本（可选）",
      "verify_cycle": true,
      "delay_after": 1.0
    }
  ],
  "verification": {
    "check_cycle_created": true,
    "expected_psi_bucket": "telegram:user_message:file_read"
  }
}
```

### 预置场景文件

| 场景 | 路径 | 验证项 |
|------|------|--------|
| File Read Success | `scripts/test_scenarios/file_read_success.json` | 文件读取成功 |
| External Failure | `scripts/test_scenarios/external_failure.json` | 失败触发 reflection |
| Cycle Strengthen | `scripts/test_scenarios/cycle_strengthen.json` | 相似消息聚合 |

---

## 4. 验证样例

### 4.1 成功 File Read 样例

```bash
# 1. 创建测试文件
mkdir -p /tmp
echo "Hello E2E Test" > /tmp/e2e_test_hello.txt

# 2. 运行测试
python scripts/telegram_sim_harness.py \
    --message "[E2E-SAMPLE] 读取文件 /tmp/e2e_test_hello.txt" \
    --verify-cycle

# 3. 验证输出
# - Reply 应包含 "Hello E2E Test"
# - State mirror 应显示新 cycle
# - psi_bucket 应为 "telegram:user_message:file_read"
```

**预期 Artifact**:
- `logs/proto_self_trace.jsonl`: 包含 event_id, timestamp, policy_hint
- `artifacts/proto_self_mirror/state.json`: cycle_store 包含 file_read cycle

### 4.2 External Failure 样例

```bash
# 1. 确保文件不存在
rm -f /tmp/e2e_not_exist_xyz.txt

# 2. 运行测试
python scripts/telegram_sim_harness.py \
    --message "[E2E-SAMPLE] 读取不存在的文件 /tmp/e2e_not_exist_xyz.txt" \
    --verify-cycle

# 3. 验证输出
# - 应触发 external_failure reflection
# - trace 中应有 reflection_trigger: external_failure
```

**验证命令**:
```bash
# 检查 reflection 触发
grep "external_failure" logs/proto_self_trace.jsonl

# 检查 state mirror
cat artifacts/proto_self_mirror/state.json | jq '.revision_counter'
```

---

## 5. 最终验证口径

### 5.1 本地模拟验证

```bash
# 运行所有预置场景
python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/file_read_success.json
python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/external_failure.json
python scripts/telegram_sim_harness.py --scenario scripts/test_scenarios/cycle_strengthen.json

# 最终验证
python scripts/regression_proto_self_telegram_e2e.py
```

### 5.2 真实 Bot API 验证

```bash
# 环境准备
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# 运行完整套件
python scripts/telegram_bot_api_e2e.py --suite file_read
python scripts/telegram_bot_api_e2e.py --suite external_failure
python scripts/telegram_bot_api_e2e.py --suite cycle_strengthen

# 验证 artifact
ls -la artifacts/proto_self_mirror/state.json
ls -la logs/proto_self_trace.jsonl
```

### 5.3 通过标准

| 验证项 | 通过标准 |
|--------|----------|
| File Read | Reply 包含文件内容，cycle 创建成功 |
| External Failure | 触发 reflection_trigger=external_failure |
| Cycle Strengthen | 相似消息命中同一 cycle_id，hits 递增 |
| Revision Counter | 每轮递增，最终值 > baseline |

---

## 6. Claude Code 自动调用

Claude Code 可直接调用这些脚本：

```python
# 本地模拟测试
!python scripts/telegram_sim_harness.py --message "读取文件 /tmp/test.txt" --verify-cycle

# 真实 Bot 测试（需配置环境变量）
!python scripts/telegram_bot_api_e2e.py --message "状态查询"
```

---

## 7. 约束与边界

- ✅ **复用现有主链**: 脚本复用 RuntimeV2Loop 和 TelegramBridge
- ✅ **测试逻辑外置**: 测试逻辑在 harness 层，不侵入主体本体
- ✅ **不破坏双核边界**: EgoCore 负责执行，Proto-Self 负责状态
- ❌ **不使用 User Account API**: 不接入 TDLib/Telethon
- ❌ **不侵入主链**: 不修改 telegram_bot.py 或 loop.py 的核心逻辑

---

*文档生成: 2026-03-24T22:30:00Z*
