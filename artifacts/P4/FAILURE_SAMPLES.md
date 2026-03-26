# P4 FAILURE_SAMPLES

| failure_id | evidence_level | source_type | artifact_path | failure | impact on P4 |
|---|---|---|---|---|---|
| P4-F-001 | E1 | code audit | [`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L150) | 旧实现会在 runtime 里单独写 host 摘要 trace，形成与 OpenEmotion trace 并行的第二写链 | 已改为优先写入统一 ledger；bridge 仅 fallback |
| P4-F-002 | E1 | code audit | [`EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py#L1) | bridge 名称和注释曾暗示自己是正式 trace 系统，职责失真 | 已降级为 compatibility-only 口径 |
| P4-F-003 | E4 | historical artifact | [`artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/replay.json`](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/replay.json#L1) | 历史 replay 只是一组文件引用，没有显式声明主账本和 trace 权威输入 | 本轮新样本起将由 `ledger.json` 显式声明 |

## 当前没有新采集失败样本的原因
- 本轮是账本治理与主链接线收口，不是新增真实渠道采样任务。
- 已有最小回归用于证明主账本与兼容镜像行为；真实渠道失败闭环仍沿用现有 failure cases，不在本轮扩展。
