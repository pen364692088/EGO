# E5 OBSERVATION_WINDOW

## 观察窗口定义

| item | value |
|---|---|
| phase | E5 |
| status | started |
| start_date | 2026-03-26 |
| timezone | America/Chicago |
| formal_chain | `Telegram -> EgoCore RuntimeV2 -> OpenEmotion` |
| source constraint | 仅 `real_telegram` / `real_channel + channel=telegram` |
| non-counted sources | simulated / integration / unit / replay-only |

## 样本计数规则

只有同时满足以下条件，才计入 E5 窗口内有效成功样本：

1. 样本必须是真实 Telegram 触发。
2. 样本必须走正式主链。
3. 样本必须具备完整 evidence bundle：
   - `raw_update`
   - `normalized_event`
   - `openemotion_result`
   - `response_plan`
   - `outbox_record`
   - `timeline`
4. 样本不得来自 simulated / integration / 手工拼装。

## 失败样本入账规则

以下情况必须记为失败样本或失败相关 gap：

- 真实触发但缺失关键 evidence
- 真实触发进入主链但发送/落账失败
- 真实触发产生异常，需要人工归因

每个失败样本必须带状态：

- `未归因`
- `已归因`
- `已复测`
- `已关闭`

## 当前窗口口径

- 2026-03-25 的真实样本全部作为历史准入底账保留
- 这些历史样本不直接计入 “E5 已完成” 口径
- 2026-03-26 起新增的真实 Telegram 主链样本，才进入 E5 窗口计数

## E5 完成条件

本次先定义完成口径，不提前宣称完成：

1. E5 窗口内累计至少 `5` 个可计数真实成功样本。
2. 至少覆盖 `2` 个不同日期的真实窗口样本，证明不是单点瞬时成功。
3. 失败账本非空，且窗口内失败样本都有状态。
4. 没有把 simulated / integration / unit 样本混入成功计数。
5. 有窗口结束报告，明确写出“能证明什么 / 不能证明什么”。

## 当前状态

- E5 已启动
- E5 窗口内有效成功样本：`0`
- E5 窗口内有效失败样本：`0`
- 历史准入底账：存在，可引用，但不充当完成证据
