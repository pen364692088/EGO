# P4 TASK_REPORT

## 任务名称
P4：Trace / Evidence / Replay 统一账本

## 任务类型
治理 / 可观测性 / 证据链收口

## 目标与成功判据
- 把 trace / evidence / replay / report 的读写路径收口为单一账本体系。
- 明确主账本、兼容镜像、replay 主输入、报告来源。
- 禁止 `ProtoSelfTraceBridge` 继续演化为第二真相源。
- 让 E2 / E3 / E4 / E5 都能落到同一账本视图。

## 当前层级
治理与科学仪器层 / host-side orchestration 层

## 当前确定项
- OpenEmotion `trace_payload` 是 Proto-Self replay 语义权威输入，而不是 EgoCore host 摘要。
- 旧主链同时存在 `TelegramEvidenceCollector` 样本目录、runtime 额外摘要 trace、bridge jsonl 三条写链。
- E2/E3/E4 历史样本已经共享一套样本包目录形态，但之前没有显式主账本声明。

## 关键未知
- 历史 E2/E3/E4 样本不会自动补出 `ledger.json`，需要后续迁移脚本或重放生成。
- 非 runtime_v2 或非 Telegram 主链是否仍有旁路 trace/evidence 写法，本轮未全量清扫。
- 观察期级别的 E5 聚合报告尚未改为直接聚合 `ledger.json`。

## 唯一主执行链
1. 审计当前 trace / evidence / replay / report 的真实读写路径
2. 指定 `ledger.json` 为 EgoCore host-side 主账本
3. 指定 `ledger.json.openemotion.trace_payload` 为 replay 主输入
4. 把 `sample.json / replay.json / tape.json / openemotion_trace.json / summary.md` 降为兼容镜像
5. 调整 runtime 主链：collector 优先入账本，bridge 仅 fallback
6. 用最小测试验证主账本与兼容回退行为

## 当前真实读写路径盘点

### 写路径
- Telegram 原始输入：[`EgoCore/app/telegram_bot.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py#L412) 调 `collector.start_sample()`
- normalized_event / openemotion_result / response_plan：[`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L150)
- external_result follow-up：[`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L230)
- outbox_record：[`EgoCore/app/telegram_bot.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_bot.py#L1091)
- 主账本与兼容镜像落盘：[`EgoCore/app/telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L435)
- 兼容 trace jsonl fallback：[`EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py#L42)

### 读路径
- Proto-Self replay 语义读取：OpenEmotion [`trace_types.py`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py#L19) 和相关 replay tests
- 历史样本 / 报告引用：`artifacts/telegram_real_mainline_v1/.../sample.json`, `replay.json`, `tape.json`
- bridge jsonl：仅历史调试 / fallback 读取，不再作为正式验收来源

## 本次改动
- 在 [`EgoCore/app/telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/telegram_evidence_collector.py#L345) 新增 `ledger.json` 主账本模型，明确：
  - 主账本 owner 是 EgoCore host evidence ledger
  - replay 权威输入是 `openemotion.trace_payload`
  - 报告来源是 `ledger.json`
  - 兼容镜像是 `sample.json / replay.json / tape.json / openemotion_trace.json / summary.md`
- 在 [`EgoCore/app/runtime_v2/proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/proto_self_runtime.py#L132) 增加 trace 收口逻辑：
  - 有 collector 时，trace 进入统一 ledger
  - 没有 collector 时，才写 `ProtoSelfTraceBridge`
- 在 [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L230) 把 external_result 也纳入同一个 collector 视图
- 在 [`EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/openemotion_adapter/proto_self_trace_bridge.py#L1) 把 bridge 明确降级为 compatibility-only
- 新增测试：
  - [`EgoCore/tests/test_telegram_evidence_collector.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_telegram_evidence_collector.py#L4)
  - [`EgoCore/tests/test_runtime_v2_proto_self_runtime.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_runtime_v2_proto_self_runtime.py#L70)

## 主账本与兼容镜像结论
- 主账本是谁
  - `artifacts/.../sample_xxx/ledger.json`
- 兼容镜像是谁
  - `sample.json`
  - `replay.json`
  - `tape.json`
  - `openemotion_trace.json`
  - `summary.md`
  - `logs/proto_self_trace.jsonl` 仅 fallback / historical mirror
- 哪些报告从哪里生成
  - 单样本摘要：从 `ledger.json` 派生
  - 样本级验收报告：以 `ledger.json` 为主，`replay.json / tape.json` 为兼容引用
  - E5 观察期聚合报告：本轮只定义应聚合 `ledger.json`，未实现新的聚合器

## E2 / E3 / E4 / E5 同一账本视图
- E2
  - 同样落 `ledger.json`
  - `evidence_level=E2`
  - 典型目录：`artifacts/telegram_real_mainline_v1/simulated/sample_*`
- E3
  - 同样落 `ledger.json`
  - `evidence_level=E3`
  - 典型目录：`artifacts/telegram_real_mainline_v1/integration/sample_*`
- E4
  - 同样落 `ledger.json`
  - `evidence_level=E4`
  - 典型目录：`artifacts/telegram_real_mainline_v1/real_telegram/sample_*`
- E5
  - 不再新发明观察期账本
  - 只允许在多个 `ledger.json` 之上做聚合报告

## 验证结果
- `python3 -m py_compile ...`：通过
- `cmd.exe /c "py -3 -m pytest tests\\test_runtime_v2_proto_self_runtime.py tests\\test_telegram_evidence_collector.py -q"`：`7 passed`

## 风险与保留项
- 历史样本尚未回填 `ledger.json`
- 非 Telegram / 非 runtime_v2 路径未在本轮全量纳管
- 现有 E4/E5 历史报告文本还未统一切到“从 ledger 聚合生成”的实现层

## 本次结论能证明什么
- 能证明 P4 已建立单一 host-side 主账本：`ledger.json`
- 能证明 replay 主输入已被明确指定为 `ledger.json.openemotion.trace_payload`
- 能证明 `ProtoSelfTraceBridge` 在 runtime 主链里已降级为 compatibility fallback，而不是正式主账本
- 能证明 E2/E3/E4 可以使用同一账本视图，E5 也已被约束为聚合同一账本而不是另起账本

## 本次结论不能证明什么
- 不能证明历史 E2/E3/E4 样本已经自动完成账本迁移
- 不能证明所有非主链模块都已经停止写旁路 trace/evidence
- 不能证明 E5 观察期聚合器已经实现并稳定运行
- 不能证明真实 Telegram 新样本已经在本轮按新 ledger 结构落盘

## 当前仍保留了哪些兼容账本
- `sample.json`
- `replay.json`
- `tape.json`
- `openemotion_trace.json`
- `summary.md`
- `logs/proto_self_trace.jsonl`

## 离 P5 还差什么
- P5 需要处理 packaging / import / 路径边界本身，本轮没有动
- 若要让历史工具只读主账本，需要在 P5 或后续任务里补齐正式导入边界与迁移工具
