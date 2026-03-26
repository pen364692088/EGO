# P4 CHANGE_PLAN

## 本轮目标
- 先盘点 trace / evidence / replay / report 的真实读写路径。
- 把宿主侧证据主账本收口为单文件 `ledger.json`。
- 保留 `sample.json / replay.json / tape.json / openemotion_trace.json / summary.md` 作为兼容镜像。
- 明确 OpenEmotion `trace_payload` 是 replay 语义权威输入，EgoCore 只负责 host-side ledger / mirror / orchestration。

## 实施顺序
1. 审计现有路径
2. 在 `TelegramEvidenceCollector` 内建立统一主账本结构
3. 让 `RuntimeV2ProtoSelfRuntime` 优先把 trace 纳入 collector，同步 external_result 路径
4. 把 `ProtoSelfTraceBridge` 降级为 compatibility-only fallback
5. 增加最小测试，卡住主账本与回退行为

## 已执行改动
- [`EgoCore/app/telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L35)
  统一主账本落盘为 `ledger.json`，并把 `openemotion_trace` 纳入完整性校验。
- [`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L132)
  trace 优先进入 collector；仅在没有 collector 时才写 `ProtoSelfTraceBridge`。
- [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L230)
  external_result 回流也带上同一个 collector。
- [`EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py#L1)
  职责口径改为 compatibility mirror。

## 明确不做
- 不改 packaging / import 边界
- 不改 README 口径
- 不处理 Telegram 输出转义断言失败
- 不推进 P5
