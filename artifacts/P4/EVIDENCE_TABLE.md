# P4 EVIDENCE_TABLE

| evidence_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
| P4-E-001 | E1 | code audit | [`EgoCore/app/telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L345) | 本轮已在 collector 内建立 `ledger.json` 主账本 | 不证明历史样本已全部迁移 |
| P4-E-002 | E1 | code audit | [`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L132) | 主链 trace 已优先进入 collector，而不是独立 bridge | 不证明所有非 runtime_v2 路径都已接同一账本 |
| P4-E-003 | E1 | code audit | [`EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py#L1) | `ProtoSelfTraceBridge` 已被明确定义为 compatibility-only | 不证明历史 jsonl 已淘汰 |
| P4-E-004 | E1 | code audit | [`OpenEmotion/openemotion/proto_self/trace_types.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py#L19) | OpenEmotion 仍持有 Proto-Self trace 语义主权 | 不证明 host 侧所有报告都已只读该语义 |
| P4-E-005 | E2 | test | [`EgoCore/tests/test_telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_telegram_evidence_collector.py#L4) | 新样本会同时生成 `ledger.json` 与兼容镜像，且 replay 主输入指向 ledger | 不证明真实 Telegram 运行时已经产出新 E4 样本 |
| P4-E-006 | E2 | test | [`EgoCore/tests/test_runtime_v2_proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_runtime_v2_proto_self_runtime.py#L70) | collector 存在时，runtime 不再把 bridge 当主账本写点 | 不证明所有异步异常路径都覆盖 |
| P4-E-007 | E2 | validation | `cmd.exe /c "py -3 -m pytest tests\\test_runtime_v2_proto_self_runtime.py tests\\test_telegram_evidence_collector.py -q"` | 7 个最小回归通过 | 不证明全仓全量回归通过 |
| P4-E-008 | E4 | historical sample | [`artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/sample.json`](/mnt/d/Project/AIProject/MyProject/Ego/artifacts/telegram_real_mainline_v1/real_telegram/sample_20260325_200847_4d2b5dae/sample.json#L1) | E4 历史样本已经具备统一样本包形态，可映射到新 ledger 视图 | 不证明历史样本自动拥有新 `ledger.json` |
