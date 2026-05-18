# E4 证据样本: sample_20260329_135400_c47a3ba2

## 基本信息

- **样本ID**: sample_20260329_135400_c47a3ba2
- **时间戳**: 2026-03-29T13:54:00.599159
- **证据层级**: V4
- **来源类型**: simulated_formal_mainline
- **渠道**: telegram

## 证据完整性

| 证据项 | 状态 |
|--------|------|
| raw_update | ✅ |
| normalized_event | ✅ |
| openemotion_result | ✅ |
| openemotion_trace | ✅ |
| response_plan | ✅ |
| outbox_record | ✅ |
| timeline | ✅ |
| tape | ✅ |
| replay | ✅ |

## 统一账本

- 主账本: `ledger.json`
- OpenEmotion trace 权威输入: `OpenEmotion trace_payload within ledger.json`
- 兼容镜像: `sample.json / replay.json / tape.json / openemotion_trace.json`

## 时间线

- 2026-03-29T13:54:00.599177: update_received
- 2026-03-29T13:54:00.725011: event_normalized
- 2026-03-29T13:54:00.725022: openemotion_processed
- 2026-03-29T13:54:00.828833: openemotion_processed
- 2026-03-29T13:54:00.929966: openemotion_processed
- 2026-03-29T13:54:00.930023: response_planned
- 2026-03-29T13:54:00.944408: message_sent

## 证明什么

- telegram 渠道消息成功进入系统
- 消息经过完整处理链路
- 生成了结构化响应

## 不证明什么

- 不证明系统稳定运行
- 不证明关键未知为无
- 不证明已完成观察期
- 不证明跨渠道一致稳定

---
*此样本由 TelegramEvidenceCollector 从 ledger.json 派生生成*
