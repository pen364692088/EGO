# Evidence Ledger

`artifacts/evidence_ledger/` 是 repo 级证据账本索引，不是新的 authority source。

正式规则：

- 项目总体状态以 [docs/PROGRAM_STATE_UNIFIED.yaml](/mnt/d/Project/AIProject/MyProject/Ego/docs/PROGRAM_STATE_UNIFIED.yaml) 为准。
- 证据账本负责记录“当前有哪些证据、强度是多少、能证明什么、不能证明什么”。
- 没有 `what_it_does_not_prove` 的 entry 视为不合格。
- 成功样本、失败样本、部分成立样本都允许入账。

字段说明：

- `evidence_id`: 稳定唯一标识。
- `status`: `pass` / `fail` / `partial`。
- `evidence_level`: `E0` 到 `E6`。
- `source_type`: `doc` / `unit` / `simulated` / `integration` / `real_channel` / `observation`。
- `artifact_path`: 仓库内 artifact 或报告路径。
- `what_it_proves`: 当前 entry 可支撑的最强结论。
- `what_it_does_not_prove`: 当前 entry 明确不能外推到哪里。
- `related_workstream`: 对应 [docs/PROGRAM_STATE_UNIFIED.yaml](/mnt/d/Project/AIProject/MyProject/Ego/docs/PROGRAM_STATE_UNIFIED.yaml) 的 workstream。
- `created_at`: 账本记录时间；若原 artifact 缺少机器时间戳，可记录 ledger ingestion time。
- `created_from_commit`: 原 artifact 明确携带的 commit，或在原 artifact 未记录时写明 `not_recorded_in_artifact`。
