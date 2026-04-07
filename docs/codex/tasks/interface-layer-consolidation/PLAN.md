# Interface Layer Consolidation - PLAN

## Task summary

把“现有能力已经存在但人难以理解、难以验证、体验像黑盒”的问题，收成 registry、acceptance chains、`/flow` canonical fields、bounded final text persistence、experience scripts 和 claim-language policy 的一组 repo-level 主线改动。

## Milestones

### Milestone 1: Registry / Drift / Claim Gate

- scope:
  - 建立 capability registry 生成器
  - 建立 drift gate 与 claim-language gate
  - 对齐 long-run task docs 与 README authority block
- files / areas likely touched:
  - `scripts/codex/build_capability_registry.py`
  - `scripts/codex/verify_capability_registry.py`
  - `scripts/codex/verify_repo.py`
  - `docs/CLAIM_LANGUAGE_POLICY.md`
  - `docs/CAPABILITY_REGISTRY.md`
  - `README.md`
  - `EgoCore/README.md`
  - `OpenEmotion/README.md`
  - `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
- acceptance:
  - registry 可生成、可校验、可在 fast verify 中阻断漂移
  - authority source 不新增第二真相源
  - 公开入口 claims 收紧到当前证据层级
- validation:
  - `python3 scripts/codex/build_capability_registry.py`
  - `python3 scripts/codex/verify_capability_registry.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - registry 和 claim gate 失败时，先回到只生成不接 gate；不要带着漂移检查推进 acceptance 链

### Milestone 2: Acceptance Chains

- scope:
  - 先补第 0 链 `subject ingress mainline`
  - 再补 5 条正式 acceptance runner
  - 写 `docs/ACCEPTANCE_CHAINS.md` 与 `docs/EXPERIENCE_SCRIPTS.md`
- files / areas likely touched:
  - `scripts/codex/run_acceptance_subject_ingress_mainline.py`
  - `scripts/codex/run_acceptance_continuity.py`
  - `scripts/codex/run_acceptance_self_model_causality.py`
  - `scripts/codex/run_acceptance_drives_causality.py`
  - `scripts/codex/run_acceptance_reflection_boundary.py`
  - `scripts/codex/run_acceptance_developmental_proactive.py`
  - `scripts/codex/_acceptance_common.py`
  - `docs/ACCEPTANCE_CHAINS.md`
  - `docs/EXPERIENCE_SCRIPTS.md`
- acceptance:
  - 六条 runner 全部能产出 `CURRENT.md + CURRENT.json`
  - 每条 current report 都写明 `what_it_proves / what_it_does_not_prove`
  - registry 的 `how_to_test` 统一指向 acceptance chain + experience script
- validation:
  - 六条 runner 分别执行一次
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note:
  - 若第 0 链证明 background/proactive 尚未收口，后续 5 条链口径统一降级为“局部成立”

### Milestone 3: `/flow` Canonical Fields + Final Text Persistence

- scope:
  - 在 response plan / evidence 层补 bounded final text persistence
  - `/flow` 增加 canonical fields 与更强的 final delivered text 审计
- files / areas likely touched:
  - `EgoCore/app/response_contract/response_plan.py`
  - `EgoCore/app/runtime_v2/proto_self_runtime.py`
  - `EgoCore/app/telegram_evidence_collector.py`
  - `EgoCore/app/telegram_bot.py`
  - `EgoCore/app/dashboard/types.py`
  - `EgoCore/app/dashboard/server.py`
  - `EgoCore/app/dashboard/static/dashboard.js`
  - `EgoCore/tests/test_dashboard_server.py`
- acceptance:
  - `/flow` 默认直接显示 canonical fields
  - final delivered text 存在 bounded preview/hash/length 或明确持久化缺失状态
  - 不再把关键主链字段埋在 engineering fields 里
- validation:
  - `python3 -m py_compile` on touched Python files
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_dashboard_server.py -q -s`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 bounded persistence 影响主链证据格式过大，优先退到 metadata-only preview/hash，不改 raw sample schema

### Milestone 4: Path/Compat Classification + Flow Continuation Audit

- scope:
  - 把现有 compat/shim 路径收成正式 path classification register
  - 给 compat register 加 drift gate，并接入 `verify_repo.py --mode fast`
  - 在 `/flow` 主视图补 `parser_source / request_mode / pending continuation` 审计字段
  - 对齐 root / EgoCore / OpenEmotion README 与 logic flow 的“边界冻结下的收口期”口径
- files / areas likely touched:
  - `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
  - `scripts/codex/verify_path_classification.py`
  - `scripts/codex/verify_repo.py`
  - `README.md`
  - `EgoCore/README.md`
  - `OpenEmotion/README.md`
  - `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
  - `docs/TELEGRAM_FLOW_VIEW_README.md`
  - `EgoCore/app/dashboard/server.py`
  - `EgoCore/tests/test_dashboard_server.py`
- acceptance:
  - compat 路径有统一分类、owner、退出条件、claim ceiling
  - fast verify 会阻断 compat/register 与公开入口的口径漂移
  - `/flow` 能直接看出 `parser_source / request_mode / pending continuation / correction_context`
  - 公开入口会明确写出当前是“边界冻结下的收口期”，compat 路径不是正式主链
- validation:
  - `python3 scripts/codex/verify_path_classification.py`
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_dashboard_server.py -q -s`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 compat drift gate 过于脆弱，先退到 required entries + public-doc references 的最小检查，不做全文案语义解析

## Progress

- current_status: conditional_complete
- current_milestone: Milestone 4 - Path/Compat Classification + Flow Continuation Audit
- milestone_state: implemented_and_verified_with_claim_ceiling

## Decision log

- 2026-04-07: 本任务按 repo-level “界面层收口里程碑”处理，不新开 WP；原因是当前主要缺口是人类界面层和审计层，不是新主体语义轴
- 2026-04-07: 第 0 链 `subject ingress mainline` 作为 admission gate，高于其他 5 条能力链；原因是 authorized event 必须先 subject-aware 才能谈 live 体验化
- 2026-04-07: final delivered text 采用 bounded preview/hash，不持久化完整 raw output；原因是要可审计但不越界
- 2026-04-07: 收口式简化第一阶段只做“分类与强约束”，不删运行时代码路径；原因是当前复杂度主因是 compat/shim 叙事混杂，不是顶层架构错误
- 2026-04-07: compat/path 分类沿用现有 `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`，不另造第二真相源；原因是要在现有文档体系上收口，而不是再长一套 register
- 2026-04-07: `/flow` continuation 审计优先落在 `Host Ingress` 主视图，而不是再新增一张新卡；原因是 parser/request_mode/continuation 本质属于 ingress 解释层

## Surprises / discoveries

- `PROGRAM_STATE_UNIFIED.yaml` 明显滞后于 2026-04-06 的 README / logic flow
- `EgoCore/README.md` 与 `EgoCore/artifacts/proto_self_v2/README.md` 在 cross-day continuity 口径上不一致，需保守对齐

## Outcomes / retrospective

- 本轮已证明：
  - capability registry / drift gate / claim-language gate 已形成 repo 级入口
  - 第 0 链 + 5 条 acceptance chain 已可一键生成 current reports
  - `/flow` 已能固定显示 canonical fields，并带 bounded final delivered text 审计面
- 还没证明：
  - provider/runtime E2E gate 的 `followup_continuity_pass` 在当前 fresh window 里未闭合
  - `verify_repo.py --mode full` 本轮未执行
- 下一步最小闭环动作：
  - 采一组 fresh follow-up continuity session，并重跑 `python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>`
  - 若要继续第二阶段简化，再单开“Proto-Self 小核收敛”任务，不在当前界面层任务内扩 scope
