# P2 FAILURE_SAMPLES

## 样本 1

| id | status | scope | source | attribution | why not P2 owner |
|---|---|---|---|---|---|
| p2_out_of_scope_telegram_status_escape | observed | Telegram status card test | `cmd.exe /c "py -3 -m pytest tests\\test_telegram_session_commands.py tests\\test_runtime_v2_ws1_turn_isolation.py -q"` | `tests/test_telegram_session_commands.py::test_status_command_returns_runtime_style_card` 断言期待未转义 markdown，而实际返回是转义文本 | 失败落点是 Telegram 输出转义文案，不是 Proto-Self state store、reset 分层或 replay 隔离 |

### 失败摘要
- 现象：断言期望 `"🦞 *EgoCore Runtime*"`，实际文本包含转义后的 `\\*`
- 影响：阻止“整组组合测试全绿”的表述
- 结论：登记为现存非 P2 归因样本，不作为本轮状态持久化失败

## 样本 2

| id | status | scope | source | attribution | why not P2 owner |
|---|---|---|---|---|---|
| p2_no_live_replay_cutover | not executed | replay runner full cutover | repository audit | 当前 replay runner 尚未全部切到 `experiments/<run>` 层 | 这是后续正式接线工作，已明确留给后续任务，不在本轮强制范围 |

### 说明
- 本轮已把 experiment/run 的隔离存储壳落地
- 但未把所有现有 replay 入口统一迁移到这一层
- 因此本轮不能声称“replay 主链已完成收口”

## 当前无 P2 直归因失败
- 新增 `test_proto_self_state_store.py` 全部通过
- `/new` 最小主链接线与 WS-1 reset 测试通过
- 当前没有发现由分层 store 直接引入的最小回归失败样本
