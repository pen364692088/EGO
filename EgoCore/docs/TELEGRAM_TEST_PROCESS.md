# Telegram Mainline Test Process

适用范围：`EgoCore` Telegram 宿主主链，包括 ingress、bridge、session state、native loop 选择、fallback、delivery、文件上传后续轮次。

目标：让任何 agent 在改 Telegram 主链后，都按同一流程验证，不再依赖“记得多测一点”。

## 1. 先判断改动触及哪一层

### 1.1 语义/桥接层

触发条件：
- 改 `app/telegram_runtime_bridge.py`
- 改 `app/runtime_v2/semantic_parser.py`
- 改 `waiting_input / execute / analyze / compare` 判定
- 改路径、附件、目标绑定、确认执行逻辑

至少跑：
- `tests/test_runtime_v2_telegram_bridge.py`
- `tests/test_runtime_v2_ws2_target_binding.py`
- `tests/test_runtime_v2_ws3_intent_guess.py`

### 1.2 会话状态机层

触发条件：
- 改 `app/telegram_bot.py`
- 改 `app/runtime_v2/state.py`
- 改 `waiting_input`、`running`、`completed_verified` 切换
- 改 follow-up / challenge / confirmation / session reset

至少跑：
- `tests/test_telegram_artifact_confirmation_flow.py`
- `tests/test_telegram_bot_native_switch.py`
- `tests/test_runtime_v2_parse_and_challenge.py`
- `tests/test_telegram_session_commands.py`
- `tests/test_telegram_context_command.py`

### 1.3 交付/结果层

触发条件：
- 改 delivery、progress、final reply、去重、status reply
- 改 `TelegramTurnReply / TelegramTurnResult`
- 改 `plan_delivery()`

至少跑：
- `tests/test_runtime_v2_telegram_delivery_actions.py`
- `tests/test_runtime_v2_typed_delivery.py`
- `tests/test_runtime_v2_failure_notice_dedupe.py`

### 1.4 文件/工具边界层

触发条件：
- 改路径白名单
- 改 file tool / tools wiring / Windows path normalize
- 改文件读写任务链

至少跑：
- `tests/test_file_tool_windows_paths.py`
- `tests/test_tools_config_wiring.py`
- `tests/test_telegram_artifact_confirmation_flow.py`

## 2. Telegram 主链最低回归门

只要改动触及 Telegram 主链，至少跑这一组：

```bash
cd EgoCore
PYTHONPATH=. python3 -m pytest -s \
  tests/test_telegram_artifact_confirmation_flow.py \
  tests/test_runtime_v2_telegram_bridge.py \
  tests/test_telegram_bot_native_switch.py \
  tests/test_runtime_v2_ws2_target_binding.py \
  tests/test_runtime_v2_ws3_intent_guess.py \
  tests/test_runtime_v2_parse_and_challenge.py \
  tests/test_telegram_session_commands.py \
  tests/test_telegram_context_command.py \
  -q
```

仓库内统一入口：

```bash
EgoCore/tools/run_telegram_mainline_regression.sh
```

## 3. 新增真实故障的处理规则

任何真实 Telegram 故障，修复前后都必须遵守：

1. 先抓真实日志 / session log / trace，不允许靠猜
2. 先写一个能复现该故障的测试，再修
3. 测试必须落在最贴近故障层级的位置
4. 修完后至少再跑一次“Telegram 主链最低回归门”
5. 如果故障来自真实用户旅程，必须优先补“跨轮状态机回归”，不能只补散点单测

## 4. 标准验证顺序

任何 Telegram 主链改动后，统一顺序如下：

1. `py_compile`
2. 对应层级的最小测试集
3. Telegram 主链最低回归门
4. 如果是外部行为变更，再做真实 Telegram E2E
5. 提交前写清：
   - 跑了哪些测试
   - 哪条是真实故障回归
   - 是否做了真实 Telegram 验证

## 5. 交接要求

交给其他 agent 时，必须明确：

- 本次改动触及哪一层
- 本次必须跑的测试集
- 是否新增了真实故障回归
- 真实 E2E 是否已做
- 若未做，缺的是什么

## 6. 禁止事项

- 不允许只跑单个新增测试就宣称“已防回归”
- 不允许用 mocked happy path 代替跨轮状态机回归
- 不允许修复真实 Telegram 故障后不补对应回归
- 不允许把测试流程留在聊天记录里，不写进仓库
