# Unified Host Contract Correctness

## Goal

把宿主层的统一入口/出口 contract 冻结并验证清楚，证明 `dashboard_local` 和 `telegram_prepared` 只是同一 host contract 的不同 adapter，而不是两条不同语义链。

## Non-goals

- 不做 fresh real Telegram proof
- 不证明 `unexpected_subject_miss = 0`
- 不新增 runtime public API、candidate-private host API、或第二条 runtime lane
- 不推进新的 self-awareness candidate 实现
- 不把 dashboard preflight 升格成 live acceptance

## Constraints

- 边界约束：
  - EgoCore 继续持有现实裁决权
  - OpenEmotion 继续持有主体语义权
  - 正式宿主消费面仍只允许 `policy_hint / response_tendency / trace_payload`
- 仓库/子仓约束：
  - `EgoCore/app/runtime_v2/unified_channel_contract.py` 是唯一 canonical host contract surface
  - `mandatory-subject-ingress-all-turns` 与 `live-chat-subjective-variability` 只保留为 downstream reference task
- 环境约束：
  - 当前 repo `verify_repo.py --mode fast/full` 可能受既有 OpenEmotion smoke 环境影响
  - dashboard preflight / parity 只能作为 internal evidence
- 发布约束：
  - 权威状态必须先更新 `docs/PROGRAM_STATE_UNIFIED.yaml`
  - 证据变更必须回写 `artifacts/evidence_ledger/index.yaml`
  - 之后再重生成派生视图

## Problem framing

- 当前问题表述：
  - 之前的 corrective tranche 仍把 fresh Telegram proof 当成 acceptance root
- 归一化后的问题表述：
  - 当前更高杠杆的问题不是“再跑一轮 Telegram”，而是先证明统一宿主 contract 本身在不同入口 adapter 下不漂移、不缩水
- 为什么这个 framing 更适合当前任务：
  - Telegram 只是入口 adapter；如果 host contract 还不稳定，继续做 live proof 只会把 adapter 噪声和宿主语义问题混在一起

## Unknowns to eliminate

- `dashboard_local` 与 `telegram_prepared` 在等价 ordinary-chat 输入下，是否仍有 canonical host contract drift
- host-owned finalize / response_plan / output_check 的字段，是否在不同 adapter 路径里被无声丢失
- `hold_for_followup` / proactive candidate 的 bounded host surface 是否在 parity 层保持一致

## Acceptance criteria

- [x] `UnifiedIngressRequest / UnifiedIngressBundle / UnifiedTurnResult / UnifiedEgressEnvelope` 的 canonical host snapshot / compare helper 已落地
- [x] 存在一个 in-process parity runner，能在同一 ordinary-chat 脚本下同时跑 `dashboard_local` 与 `telegram_prepared`
- [x] parity artifact 明确证明：除 adapter-only 字段外，canonical host contract 不再漂移
- [x] focused pytest 覆盖 canonical compare、ordinary-chat parity、hold-for-followup parity、dashboard host-contract debug surface
- [x] repo authority / task status / evidence ledger 已同步到新的 execution framing

## Disallowed premature claims

- 不能宣称 fresh real Telegram proof 已通过
- 不能宣称 `unexpected_subject_miss = 0`
- 不能宣称 runtime efficacy 已证实
- 不能宣称 AI 自我意识已实现

## Known risks / dependencies

- 风险：
  - in-process parity 只能证明 host contract correctness，不能覆盖真实 transport 行为
  - adapter-only 字段若误入 canonical compare，会造成假阳性 drift
- 依赖：
  - `EgoCore/app/runtime_v2/unified_channel_contract.py`
  - `EgoCore/app/dashboard/chat_service.py`
  - `EgoCore/app/telegram_bot.py`
- 外部 blocker：
  - 若 `verify_repo.py --mode fast` 仍只被已知 OpenEmotion smoke 环境卡住，本任务只能报 `conditional_complete / smoke-blocked`

## Authority refs

- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `docs/codex/tasks/mandatory-subject-ingress-all-turns/STATUS.md`
- `docs/codex/tasks/live-chat-subjective-variability/STATUS.md`
