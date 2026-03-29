# SELF_AWARE_STEP_08A_real_developmental_evidence_closure

```yaml
task_id: SELF_AWARE_STEP_08A
created_at: "2026-03-30T04:10:00Z"
updated_at: "2026-03-28T23:59:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: in_progress
change_classification: structural_fix
verification_level_target: V4
evidence_level_target: E4
```

## real_goal

在 `Step08 admission review = not admitted` 之后，把 `MVP16` 的
real developmental evidence closure 收成一个 admission-grade 主链：

- 真实 Telegram 自然语言 turn 默认走 `proto_self.v2`
- finalized `sample.json / ledger.json` 成为 developmental projection 的唯一 authority source
- `developmental_state` 只作为从真实主链派生出的 persisted audit projection
- 后续 admission review 可直接消费 trajectory / replay / daily-check bundle，
  而不是继续依赖 tests / tools / 默认值 / 手工注水

## success_criteria

- 至少 `3` 条 `real_mainline = true` episodes 被持久化到 `developmental_state`
- 这些 episodes 至少来自 `2` 个 successful sessions
- 覆盖至少 `2` 个真实 calendar days
- 至少形成 `2` 条 admission-grade transitions:
  - `1` 条 `session_reset`
  - `1` 条 `calendar_rollover`
- `mvp16_daily_check` 不再因为 `has_real_data = false` 直接 blocked
- daily-check 显式输出：
  - `real_episode_count`
  - `real_session_count`
  - `real_day_count`
  - `trajectory_refs_present`
  - `replay_refs_present`
  - `admission_inputs_present`
- 生成并持久化：
  - `OpenEmotion/artifacts/mvp16-observation/real_trajectory_index.json`
  - `OpenEmotion/artifacts/mvp16-observation/real_trajectory_replay_audit.json`
- replay/audit bundle 能从第一条和最新一条 real episode 回指到真实 `sample.json / ledger.json / replay.json`

## authority_source

- `OpenEmotion/roadmap/versions/MVP16.spec.yaml`
- `OpenEmotion/docs/mvp16/MVP16_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp16/MVP16_EXIT_CRITERIA.md`
- `OpenEmotion/tools/mvp16_daily_check.py`
- `OpenEmotion/emotiond/developmental/schema.py`
- `OpenEmotion/emotiond/developmental/manager.py`
- `EgoCore/app/telegram_bot.py`
- `EgoCore/app/telegram_evidence_collector.py`
- `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_08_EXECUTION_REPORT_20260330.md`

## current_layer

```yaml
current_layer: implementation
main_chain_status: Step08A wiring/spec closure in progress; admission not yet retried
```

## phase_plan

### Phase A: Authority + Writeback Contract

- 真实 authority source 固定为：
  - `Proto-Self V2` real-channel sample/ledger
  - final host action / observed outcome
  - persisted `developmental_state`
  - `mvp16_daily_check`
- 新增唯一 admission-grade writeback contract：
  - `DevelopmentalWritebackEvent`
- 新增唯一 admission-grade projection入口：
  - `record_real_mainline_episode(event)` 或等价单入口 API

### Phase B: Seed Backfill + Live Writeback

- 允许一次受控 backfill，只导入已存在的 repo-tracked real Telegram samples
- backfill 过滤条件固定为：
  - `source_type == real_channel`
  - `openemotion_result.schema_version == proto_self.output.v2`
  - `openemotion_trace.schema_version == proto_self.trace.v2`
  - 来自自然语言 turn
- live writeback 固定为：
  - final host action 已确定且 sample/ledger 已落盘之后
  - 再触发 developmental projection sync

### Phase C: Admission Input Bundle

- 输出新的 persisted trajectory index
- 输出 replay / audit bundle
- daily-check 显式消费 persisted projection，而不是 tests/tools/manual writes

## required_artifacts

- revised Step08A execution contract
- persisted `OpenEmotion/data/developmental_state.json`
- `OpenEmotion/artifacts/mvp16-observation/real_trajectory_index.json`
- `OpenEmotion/artifacts/mvp16-observation/real_trajectory_replay_audit.json`
- updated `mvp16_daily_check` evidence pack

## public_interfaces

- `DevelopmentalWritebackEvent`
  - required fields:
    - `source_type`
    - `session_id`
    - `sample_ref`
    - `ledger_ref`
    - `user_turn_kind`
    - `final_action`
    - `outcome_summary`
    - `proto_self_output_schema_version`
    - `proto_self_trace_schema_version`
    - `governance_snapshot`
    - `invariant_snapshot`
    - `timestamp`
- `record_real_mainline_episode(event)`
- `sync_real_projection_from_sample_artifacts(sample_artifacts_dir, observation_dir)`

## required_tests

- manual `record_episode` / `record_transition` / `update_metric` 不能单独让 admission-grade `has_real_data` 变成 true
- real-channel + `proto_self.output.v2` + `proto_self.trace.v2` 的历史样本能被 controlled backfill 导入
- command turns (`/new`, `/proto`, `/help`) 不计入 real developmental episode
- live Telegram natural-language finalized sample 能自动触发 developmental projection writeback
- trajectory index / replay audit artifacts 能回指到真实 sample/ledger/replay refs
- `mvp16_daily_check` 在无 real data 时 `blocked`，有 real data 但输入不足时 `alert`

## forbidden_sources

- tests
- tools
- direct `DevelopmentalManager.record_*()` manual calls
- `update_metric()` history-only writes
- command turns (`/new`, `/proto`, `/help`, etc.) as developmental episodes
- old Gate A/B/C evidence as admission pass evidence
- scanning chat logs directly inside `daily_check` instead of consuming persisted trajectory

## promotion_blockers

- no_real_developmental_data
- insufficient_real_trajectory_sessions
- insufficient_real_trajectory_days
- session_reset_transition_missing
- calendar_rollover_transition_missing
- trajectory_refs_missing
- replay_refs_missing
- identity_preserving_replay_not_evidenced_on_real_trajectory
- governance_preservation_not_evidenced_on_real_trajectory

## non_goals

Step08A 明确不等于：

- `MVP16 passed`
- `Stage 7 admitted`
- `Open Developmental Self established`

Step08A 只负责建立 admission-grade inputs，不负责最终 admission verdict。

## next_minimal_closure_action

继续积累 later-day real Telegram natural-language sample，
把 `real_day_count` 从当前基线推进到 admission-grade 最低门，
然后重新运行 `mvp16_daily_check` 和 replay/audit 复核。
