# Repo Authority Cleanup - PLAN

## Task summary

把全仓收成“一个正式主链 + 一组单一 authority + 一套 canonical docs + 一条 archive 边界”。当前任务状态已收口为 `repo_authority_cleanup: closeout-complete (repo/integration scope)`；remaining items only live in `optional housekeeping / future cleanup backlog`.

## Milestones

### Milestone 1: Phase 0 Truth Map + Identity Baseline + Self-Model Wave

- scope:
  - 建立 long-run task package 与 6 个 ledger
  - 盘点 formal mainline、authority/substrate、compat/shim/mirror/reference/archive/delete-candidate
  - 复核 `identity` 已落地的单一 runtime authority 波次
  - 若 formal caller 与 active substrate 已足够清楚，则做 `self-model` 代码级 authority demotion
  - 把 `proto_self_restore / self_model_adapter / self_model_mirror` 等明显非 formal caller 路径写入 fate ledger 与 conflict register
- files / areas likely touched:
  - `docs/codex/tasks/repo-authority-cleanup/*`
  - `OpenEmotion/openemotion/self_model/*`
  - `OpenEmotion/emotiond/self_model_adapter.py`
  - `OpenEmotion/emotiond/self_model_mirror.py`
  - `OpenEmotion/tests/*single_authority*.py`
  - `scripts/codex/verify_proto_self_single_authority.py`
- acceptance:
  - 6 个 ledger 首版完成
  - `identity` wave 与 single-authority docs/gate 对齐
  - `self-model` formal owner/active substrate/compat/reference 代码级边界明确
  - formal mainline 不变，legacy adapter/mirror 未被 formal caller 使用
- validation:
  - `python3 -m py_compile` on touched files
  - `cd OpenEmotion && <repo runtime> -m pytest tests/test_identity_single_authority.py tests/test_self_model_single_authority.py openemotion/proto_self_v2/tests/test_self_model_read_integration.py -q`
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_runtime_v2_proto_self_runtime.py -k "self_model or identity" -q -s`
  - `python3 scripts/codex/verify_proto_self_single_authority.py`
  - `python3 scripts/codex/verify_path_classification.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 self-model 波触发 stop 条件，则回退到仅保留 Phase 0 + identity authority ledger，不带 self-model 代码改动进入提交

### Milestone 2: Drives / Reflection / Developmental Classification

- scope:
  - 不改语义，只补 drives/reflection/developmental 的 caller matrix、conflict register、file fate admission
  - 仅在 Milestone 1 完成且未引入新 dual-authority 风险时推进
- files / areas likely touched:
  - `docs/codex/tasks/repo-authority-cleanup/*`
  - 必要时 `scripts/codex/verify_proto_self_single_authority.py`
- acceptance:
  - drives/reflection/developmental 的 current authority / substrate / implementation library 在 ledger 中清楚
  - 明确哪些路径后续可进入删除 admission，哪些必须保留
- validation:
  - `python3 scripts/codex/verify_proto_self_single_authority.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 caller proof 不充分，只保留 conflict register，不推进 fate 决策

### Milestone 3: Canonical Docs / Artifact Admission

- scope:
  - 建立 canonical docs 索引与 artifacts/log inventory
  - 只做索引与归档 admission，不在本任务前段直接物理搬迁
- files / areas likely touched:
  - `docs/codex/tasks/repo-authority-cleanup/CANONICAL_DOCS_INDEX.md`
  - `docs/codex/tasks/repo-authority-cleanup/ARTIFACT_LOG_INVENTORY.md`
  - public docs only if canonical pointers need tightening
- acceptance:
  - canonical docs 集合明确
  - current evidence 与 archive candidates 明确
  - canonical/archive boundary marker 已建立
  - cleanup admission gate 能拦住 canonical/docs/artifact 边界漂移
- validation:
  - `python3 scripts/codex/verify_cleanup_admission.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 docs/artifacts 存在 caller 不明的引用，不做物理移动

### Milestone 4: Delete Admission Proof and Generated/Docs Cleanup

- scope:
  - 继续推进 `proto_self_restore / self_model_adapter / self_model_mirror` 的 generated/docs/tool caller 清理
  - 对 `self_model_adapter / self_model_mirror` 完成 delete-admission finish wave，必要时物理删除
- acceptance:
  - 至少一个 delete-candidate 的非 formal caller 进一步收窄，且 self_model_adapter / self_model_mirror 达到 delete-ready 或已物理删除
  - 不引入 formal mainline 回退
- validation:
  - scoped tests
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 generated/docs/tool caller 迁移不清晰，则只更新 ledger，不删文件；若已无 compat consumer，则优先物理删除 self_model_adapter / self_model_mirror

### Milestone 5: Clean-Clone / CI Final Closeout Proof

- scope:
  - 固化 canonical/archive/current/archive/generated/dirty-worktree admission boundary
  - 准备 clean-clone / CI final closeout proof surface
  - 不做新的 authority cleanup，不做物理 archive moves
- files / areas likely touched:
  - `docs/codex/tasks/repo-authority-cleanup/*`
  - `docs/canonical/README.md`
  - `docs/archive/README.md`
  - `artifacts/current/README.md`
  - `artifacts/archive/README.md`
  - `EgoCore/docs/generated/README.md`
  - `scripts/codex/verify_cleanup_admission.py`
  - `EgoCore/tools/build_doc_system_inventory.py`
  - `EgoCore/tests/test_doc_system_inventory_builder.py`
- acceptance:
  - canonical/archive/current/archive/generated/dirty-worktree boundaries are explicit in repo-tracked docs
  - cleanup admission gate enforces the boundary texts
  - next minimal action is clean-clone / CI final closeout proof, not more authority cleanup
- validation:
  - `python3 scripts/codex/verify_cleanup_admission.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - scoped generated inventory builder tests
- rollback note:
  - 若 clean-clone / CI proof surface 不足，只保留 boundary docs 和 gate，不做 physical archive moves

## Progress

- current_status: complete
- current_milestone: repo_authority_cleanup: closeout-complete (repo/integration scope)
- milestone_state: complete

## Optional housekeeping / future cleanup backlog

- 仅作为后续可选 housekeeping，不属于本任务 closeout 范围
- 可能的后续项：
  - archive/reference-only docs further compression
  - optional physical archive of non-authoritative proof surfaces
  - any future non-authoritative generated-residue tidy-up

## Decision log

- 2026-04-08: 本任务按 long-run cleanup program 执行，不做一次性大删库；原因是 formal mainline 与 current evidence chain 不能被清理动作打断
- 2026-04-08: 第一轮固定只做 `Phase 0 + identity authority wave + self-model authority wave`；原因是 drives/reflection/developmental 仍有更高 dual-layer 风险，不能一轮混改
- 2026-04-08: `identity` authority wave 已落地；当前已落地代码波次作为 resolved runtime authority 复核与 ledger 对齐对象，`openemotion.identity.*` 保持 reference-only
- 2026-04-08: docs/artifacts 先做索引与 fate ledger，不先做物理迁移；原因是当前 scripts/gates/artifacts caller 仍分散
- 2026-04-08: `proto_self_restore` 的 package re-export 可以安全移除；原因是全仓 caller 证明已显示代码 caller 只剩 `__init__.py` 自身，formal mainline 为 0
- 2026-04-08: canonical/docs/artifact 先建立 boundary marker 和 gate，不做物理迁移；原因是当前 docs/scripts/artifacts 仍存在大量路径引用，先锁 admission 比盲目搬迁更安全
- 2026-04-08: clean-clone / CI final closeout proof 必须显式包含 generated-residue cleanup；原因是 settled targeted tests 会写入 repo-tracked generated files（尤其 `EgoCore/docs/generated/*` 与 `OpenEmotion/artifacts/mvp12/*`），不先 restore/remove 再验 clean 会导致 proof overclaim
- 2026-04-08: `proto_self_restore` 的 generated import-map stale edge 已通过重新生成 inventory 清除；原因是 package re-export 移除后，继续保留旧 generated caller 会误导 delete admission 结论
- 2026-04-08: `proto_self_restore` 已在 residue wave 中物理删除；原因是 formal caller = 0，generated import-map stale edge 已清，generated file inventory residue 也已清除
- 2026-04-08: `mvp13_daily_report.py` 已改为 archive-based 历史报告，不再真实 import mirror；原因是 legacy report 继续持有 live mirror import 会污染 delete admission 口径
- 2026-04-08: `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 中 `OE_MVP:13` 的 evidence 已收紧为 archive report，不再引用 live `emotiond/self_model_adapter.py` 文件路径；原因是当前 authority source 不应继续把 legacy adapter 文件暴露成 current evidence surface
- 2026-04-08: 5 份 archive self-model 文档内部的“主链/接入/可用”旧口径已清理为历史 shadow / legacy compatibility snapshot 表述；原因是 archive docs 不应继续冒充 current formal mainline
- 2026-04-08: archive self-model 文档中残留的 `docs/E2E_SELF_MODEL_ADAPTER_REPORT.md` 已统一改回 `docs/archive/E2E_SELF_MODEL_ADAPTER_REPORT.md`，`main_chain_wiring_check.py` 也固定为 historical snapshot 口径；原因是 archive surface 不应继续引用非 archive 路径或暗示 live wiring verifier
- 2026-04-08: `e2e_self_model_adapter.py` 的口径已明确为“读取 legacy artifact directory 中 historical shadow artifacts 的 archive report”；原因是它仍读取旧 shadow artifact 目录，但不应再被误读成 live adapter exercise surface
- 2026-04-08: `main_chain_wiring_check.py`、`e2e_self_model_adapter.py`、`mvp13_daily_report.py` 已在 caller/fate ledger 中明确为 archive/reference-only surfaces，并从 `self_model_adapter / self_model_mirror` 的 remaining caller lists 中拆出；原因是它们是历史报告工具，不应再被计为 live callers
- 2026-04-08: `verify_mvp15_mainline_wiring.py`、`mvp15_funnel_check.py`、`mvp15_funnel_tracker.py`、`mvp15_daily_validation.sh`、`setup_mvp15_cron.sh` 已在 caller/fate ledger 中明确为 archive/reference-only surfaces；原因是它们是 MVP15 历史验证/趋势/包装工具，不应再被计为 live callers
- 2026-04-08: `OpenEmotion/emotiond/core.py` 已移除 `emotiond.self_model_adapter` / `emotiond.self_model_mirror` 的 live import 与 shadow side-effect 调用，bias 读取改为 formal owner `SelfModelStore` 优先；`OpenEmotion/tools/dual_repo_closed_loop_e2e.py` 已降为 archive/proof-only harness，不再导入或实例化 live adapter；原因是这波只做 legacy caller consolidation，不改变 formal mainline 语义
- 2026-04-08: `OpenEmotion/tests/mvp13/test_owner_backed_decision_surface.py` 与 `OpenEmotion/tests/mvp13/test_behavioral_influence_formal_proof.py` 已迁到 formal owner store proof path，不再依赖 live adapter 注入；原因是 proof harness 需要与当前单一 authority 对齐，避免继续把 adapter 伪装成 live surface
- 2026-04-08: `self_model_adapter` / `self_model_mirror` delete-admission finish wave 已完成：`OpenEmotion/tests/test_self_model_single_authority.py` 已改为更弱的 ledger/file-fate/admission test，legacy adapter/mirror 已物理删除，当前 docs/path register/program-state 已不再把它们叙述成 live-ish blockers
- 2026-04-08: reflection legacy caller wave 已收口：`OpenEmotion/emotiond/core.py` 不再使用 `reflection_shadow`，reflection guidance 已改为 formal owner store-backed read；`OpenEmotion/tools/causal_intervention_experiments.py` 已降为 archive/reference-only reflection probe，`emotiond/reflection.py` 只保留 thin trigger/report substrate；原因是 reflection legacy runtime callers 必须移出 live authority 叙事，但当前 formal owner/report split 仍需保留最薄触发层
- 2026-04-08: drives authority wave 已收口：`openemotion.endogenous_drives/*` 为唯一 formal owner，`OpenEmotion/emotiond/drive_adapter.py` 与 `OpenEmotion/emotiond/drives/*` 仅保留 compat/projection/helper surfaces，`OpenEmotion/openemotion/proto_self/appraisal.py + DriveField` 只保留 thin substrate；原因是 drives/appraisal 不能继续被写成 unresolved later wave
- 2026-04-08: developmental authority wave 已收口：`openemotion.developmental_self/*` 为唯一 formal owner，`OpenEmotion/emotiond/developmental_core/*` 继续作为 implementation library，`OpenEmotion/openemotion/proto_self_v2/developmental_self_context.py` / `OpenEmotion/openemotion/proto_self_v2/developmental.py` / `EgoCore/app/runtime_v2/proto_self_runtime.py::_apply_developmental_self_writeback` 形成 live caller path，`OpenEmotion/emotiond/developmental/*` 与 `OpenEmotion/tests/mvp16/*` 仅保留 compat/reference / proof-e2e 角色；原因是 developmental 是单一 authority + implementation library split，不是双主也不是 dead code

## Surprises / discoveries

- 当前 worktree 已存在大量与本任务无关的脏文件；提交时必须严格 scoped
- `self-model` legacy adapter/mirror 当前 formal caller 为 0，但仍有 tools/docs/generated caller
- `proto_self_restore.py` formal caller 为 0，但已物理删除；`EgoCore/app/openemotion_adapter/__init__.py` 的 re-export 与 generated import-map/file inventory residue 都已清掉
- `proto_self_restore.py` 当前已 delete-done，不再是 blocker

## Outcomes / retrospective

- 本轮已证明：
  - `identity` authority wave 已在代码级收口，可直接作为 Phase 0 基线
  - `self-model` formal owner 已在 current mainline 上被 runtime 注入与 writeback 消费；legacy adapter/mirror 不在 formal caller 上
  - `drives` formal owner 已在 current mainline 上通过 compat/projection helper 被消费；legacy wrapper surfaces 不在 formal caller 上
- 还没证明：
  - `proto_self_restore` 已完成 delete-done，不再作为 blocker
  - `developmental_core` 是否还需要进一步收缩实现库或 wrapper surfaces
- 下一步最小闭环动作：
  - 继续收窄 `self_model_adapter / self_model_mirror` 的 authority-source/docs caller；archive report tools 已单独归档，不再计入这两个 delete-admission blocker
  - `proto_self_restore` 不再作为后续低风险切片
  - developmental 这一波只做 ledger / verifier / documentation 收口，不再回动 runtime semantics
