# Repo Authority Cleanup - STATUS

## Current milestone

- name: Milestone 4 - Delete Admission Proof and Generated/Docs Cleanup
- owner: Codex
- state: in_progress

## Current state

- current_layer: repo_authority_cleanup
- main_chain_status: phase0_truth_map_landed_identity_baseline_confirmed_self_model_authority_wave_landed_milestone2_classification_landed_milestone3_admission_landed_milestone4_proto_self_restore_generated_edge_cleared_self_model_mirror_tool_import_removed_mvp13_report_archive_based_e2e_adapter_report_archive_based_archive_self_model_docs_clarified_proto_self_restore_inventory_residue_only_oe_mvp13_archive_evidence_only_archive_self_model_body_clarified_archive_self_model_paths_clarified_e2e_adapter_legacy_artifact_dir_clarified_self_model_adapter_core_and_dual_repo_live_callers_removed_mvp13_proof_tests_migrated_to_formal_owner_store_self_model_delete_admission_finished_adapter_mirror_deleted_reflection_legacy_runtime_callers_removed_reflection_probe_archive_only_reflection_trigger_substrate_retained
- completion_class: conditional_complete

## Completed work

- 已创建 long-run task package：`docs/codex/tasks/repo-authority-cleanup/`
- 已确认当前 formal mainline 不变：`native_hooks -> proto_self_runtime -> proto_self_adapter -> proto_self_v2/kernel`
- 已确认 `identity` 代码级单一 authority baseline 已存在，可直接作为本轮基线复核
- 已确认 `self-model` formal owner 当前在主链上被 runtime projection/writeback 消费
- 已确认 `proto_self_restore.py` 当前 formal caller 为 0，但仍存在 tools/docs/generated caller；`emotiond/self_model_adapter.py`、`emotiond/self_model_mirror.py` 已物理删除
- 已完成 Phase 0 六个 ledger 首版落地：`AUTHORITY_MATRIX / CALLER_MATRIX / FILE_FATE_LEDGER / CANONICAL_DOCS_INDEX / ARTIFACT_LOG_INVENTORY / CONFLICT_REGISTER`
- 已完成 `self-model` 代码级 authority 收口：formal owner 自证、legacy adapter/mirror 自降级、single-authority static regression 落地
- 已完成 `drives / reflection / developmental` 的 caller/authority ledger 收口，不改语义
- 已移除 `EgoCore/app/openemotion_adapter/__init__.py` 中对 `ProtoSelfRestore` 的 package re-export；当前只剩 docs/generated residue
- 已建立 canonical/archive boundary marker：`docs/canonical/README.md`、`docs/archive/README.md`、`artifacts/current/README.md`、`artifacts/archive/README.md`
- 已新增 cleanup admission gate：`scripts/codex/verify_cleanup_admission.py`
- 已重新生成 `EgoCore/docs/generated/*`，清除 `proto_self_restore` 的 generated import-map stale edge；当前剩余 residue 收窄为 generated file inventory
- 已移除 `OpenEmotion/tools/main_chain_wiring_check.py` 对 `emotiond.self_model_mirror` 的真实 import；`OpenEmotion/tools/mvp13_daily_report.py` 也已改为 archive-based，不再真实 import mirror
- 已将 `OpenEmotion/tools/e2e_self_model_adapter.py` 改为 archive/reference-only 报告，不再导入 live adapter
- 已把 `OpenEmotion/tools/main_chain_wiring_check.py`、`OpenEmotion/tools/e2e_self_model_adapter.py`、`OpenEmotion/tools/mvp13_daily_report.py` 在 caller/fate ledger 中明确为 archive/reference-only surfaces，不再计为 live callers
- 已把 `OpenEmotion/tools/verify_mvp15_mainline_wiring.py`、`OpenEmotion/tools/mvp15_funnel_check.py`、`OpenEmotion/tools/mvp15_funnel_tracker.py`、`OpenEmotion/tools/mvp15_daily_validation.sh`、`OpenEmotion/tools/setup_mvp15_cron.sh` 在 caller/fate ledger 中明确为 archive/reference-only surfaces，不再计为 live callers
- 已把 `OpenEmotion/tools/dual_repo_closed_loop_e2e.py` 文案明确降级为 legacy compatibility harness；`OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 中 `OE_MVP:13` 也已收紧为历史 shadow 证据口径
- 已将 `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 中 `OE_MVP:13` 的 evidence 收紧为 archive report，不再直接引用 live `emotiond/self_model_adapter.py` 文件路径
- 已为 5 份 archive self-model 证明文档补充历史快照声明，明确它们不代表当前 formal mainline 或当前 authority
- 已进一步清理 5 份 archive self-model 文档内部的“主链/接入/可用”旧口径，统一改成历史 shadow / legacy compatibility snapshot 表述
- 已将 archive self-model 文档中残留的非 archive 报告路径改回 `docs/archive/...`，并把 `main_chain_wiring_check.py` 固定为 historical snapshot 口径
- 已将 `OpenEmotion/tools/e2e_self_model_adapter.py` 明确为读取 legacy artifact directory 中 historical shadow artifacts 的 archive report，不再容易被误读成 live adapter exercise surface
- 已将 `OpenEmotion/emotiond/core.py` 中 `emotiond.self_model_adapter` / `emotiond.self_model_mirror` 的 live import 和 shadow side-effect 调用移除，bias 读取改为 formal owner `SelfModelStore` 优先
- 已将 `OpenEmotion/tools/dual_repo_closed_loop_e2e.py` 降级为 archive/proof-only harness，不再导入或实例化 live adapter
- 已将 `OpenEmotion/tests/mvp13/test_owner_backed_decision_surface.py` 与 `OpenEmotion/tests/mvp13/test_behavioral_influence_formal_proof.py` 迁到 formal owner store proof path，不再依赖 live adapter 注入
- 已将 `OpenEmotion/tests/test_self_model_single_authority.py` 重写为更弱的 ledger/file-fate/admission test，不再 import legacy adapter/mirror modules
- 已确认 `OpenEmotion/emotiond/self_model_adapter.py` 与 `OpenEmotion/emotiond/self_model_mirror.py` 已物理删除，当前 delete-ready 结论已升级为 delete-done
- 已完成 reflection legacy caller wave：`OpenEmotion/emotiond/core.py` 不再依赖 `reflection_shadow`，reflection guidance 改为 formal owner store-backed read；`OpenEmotion/tools/causal_intervention_experiments.py` 已降为 archive/reference-only reflection probe；`emotiond/reflection.py` 仅保留 thin trigger/report substrate

## Last validation results

- mode: milestone-4 scoped verification
- result: passed
- summary:
  - `cmd.exe /c "OpenEmotion\\.venv\\Scripts\\python.exe -m pytest OpenEmotion\\tests\\test_self_model_single_authority.py -q"` -> `9 passed`
  - `python3 -m py_compile OpenEmotion/tests/test_self_model_single_authority.py`
  - `python3 scripts/codex/verify_repo.py --mode fast` -> passed
  - scoped `git diff --check` -> passed

## Decisions made

- 第一轮 milestone 固定为 `Phase 0 + identity baseline closeout + self-model authority wave`
- `identity` 本轮不重复设计，只做 ledger/doc/gate 对齐
- `self-model` 本轮采取最小代码收口：formal owner 自证 + legacy adapter/mirror 自降级 + no-dual-authority static assertion
- `drives / reflection / developmental` 第一轮只进 ledger 与 conflict register，不进语义改造
- `self-model` 本轮后的唯一 authority 固定为 `openemotion.self_model/*`；`openemotion.proto_self.self_model` 仅保留 active compute/proposal substrate 角色
- `emotiond/self_model_adapter.py` 固定为 `compatibility_only`，`emotiond/self_model_mirror.py` 固定为 `reference_only`
- `drives / reflection / developmental` 本轮只做 caller/authority 定性，不改 owner/substrate 语义
- `proto_self_restore` 当前 formal caller 仍为 0，且 package re-export 已被清除；删除 admission 现在只剩 generated file inventory residue
- `proto_self_restore` 当前 formal caller 仍为 0，package re-export 与 generated import-map stale edge都已清除；删除 admission 现在只剩 generated file inventory residue
- `self_model_mirror` 当前仍有 legacy daemon callers，但 archive report tools 已从 remaining caller lists 中退出；`main_chain_wiring_check.py` / `mvp13_daily_report.py` 不再作为真实 code caller，`OE_MVP:13` 也不再把 adapter 口径写成 current mainline
- `dual_repo_closed_loop_e2e.py` 当前被明确标成 legacy compatibility harness，不再允许被误读为 formal mainline verifier
- `e2e_self_model_adapter.py` 当前被明确标成 archive/reference-only 报告，不再允许被误读为 live adapter exercise harness
- `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 当前不再把 live `emotiond/self_model_adapter.py` 文件路径列为 `OE_MVP:13` evidence
- canonical/docs/artifact 当前只建立 admission boundary，不做物理迁移
- archive self-model 文档当前只保留历史快照表述，不再把旧 wiring 结果写成 current formal mainline
- archive self-model 文档当前也不再把 SelfModelAdapter 报告路径指向非 archive 文档位置
- `e2e_self_model_adapter.py` 当前虽仍读取 `artifacts/self_model_adapter`，但口径已明确为 legacy artifact directory 上的历史归档报告

## Open risks

- worktree 脏文件很多，提交必须极度 scoped
- `proto_self_restore` 当前虽已无代码 caller，但 generated file inventory residue 仍在，不能直接删
- `proto_self_restore.py` 当前 formal caller 为 0，但 generated file inventory residue 仍在，因此还不能报 delete-ready
- reflection legacy runtime caller 已收口，当前只剩 `emotiond/reflection.py` 的 thin trigger/report substrate 与 archive/reference-only probe surface；reflection 本体不再是 delete blocker，但 trigger substrate 是否保留仍待后续 dedicated wave 决定
- archive self-model docs 已完成降噪，当前不再是 blocker
- `self-model` dual-authority 已收口；`self_model_adapter.py` 与 `self_model_mirror.py` 已物理删除，当前不再是 delete-ready blocker
- artifacts/logs 仍未物理迁移；archive/current 目录现在只是 boundary marker

## Next step

- 当前下一步：继续做 `delete admission proof and generated/docs cleanup`，优先处理 `proto_self_restore` 的 generated/docs residue；`drives / reflection / developmental` 仍不改语义
- 当前下一步：`dual_repo_closed_loop_e2e.py` 已转 archive/proof-only harness，下一步只需维持其 archive-only 口径，不再把它当 live blocker
- 当前下一步：reflection legacy runtime caller 已收口，若继续推进只能决定是否把 `emotiond/reflection.py` 也纳入后续 trigger-substrate retirement 波；当前波次不再把 MVP15 archive 工具视为 blocker

## Commands run / evidence

- `sed -n '1,220p' PROJECT_MEMORY.md`
- `sed -n '1,220p' docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `sed -n '1,220p' docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md`
- `sed -n '1,240p' README.md`
- `sed -n '1,240p' EgoCore/README.md`
- `sed -n '1,240p' OpenEmotion/README.md`
- `sed -n '1,220p' docs/codex/README.md`
- `python3 scripts/codex/new_task.py repo-authority-cleanup --title "Repo Authority Cleanup"`
- `sed -n '1,260p' docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
- `sed -n '1,260p' docs/PROTO_SELF_MVP_AUTHORITY_AUDIT.md`
- `sed -n '1,260p' EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
- `find docs -maxdepth 2 -type f`
- `find artifacts -maxdepth 2`
- `find OpenEmotion/artifacts -maxdepth 2`
- `find EgoCore/artifacts -maxdepth 2`
- targeted `rg` on `self_model_adapter / self_model_mirror / proto_self_restore / identity_invariants / developmental_core`
- `rg -n "openemotion\\.endogenous_drives|endogenous_drive_context|DriveField|proto_self\\.appraisal" EgoCore/app OpenEmotion/openemotion/proto_self_v2 OpenEmotion/openemotion/proto_self OpenEmotion/tests OpenEmotion/tools`
- `rg -n "openemotion\\.reflective_self|reflective_self_context|proto_self\\.reflection|reflection_note|emotiond\\.reflection|self_counterfactual" EgoCore/app OpenEmotion/openemotion/proto_self_v2 OpenEmotion/openemotion/proto_self OpenEmotion/emotiond OpenEmotion/tests OpenEmotion/tools`
- `rg -n "openemotion\\.developmental_self|developmental_self_context|emotiond\\.developmental_core|openemotion\\.endogenous_drives|openemotion\\.reflective_self" .`
- `rg -n "ProtoSelfRestore|proto_self_restore" .`
- `python3 -m py_compile EgoCore/app/openemotion_adapter/__init__.py EgoCore/tests/test_openemotion_adapter_shims.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_openemotion_adapter_shims.py -q -s`
- `python3 -m py_compile scripts/codex/verify_cleanup_admission.py`
- `python3 scripts/codex/verify_cleanup_admission.py`
- `python3 EgoCore/tools/build_doc_system_inventory.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_doc_system_inventory_builder.py -q -s`
- `python3 -m py_compile OpenEmotion/tools/mvp13_daily_report.py OpenEmotion/tools/dual_repo_closed_loop_e2e.py OpenEmotion/tests/test_self_model_single_authority.py`
- `cmd.exe /c "OpenEmotion\\.venv\\Scripts\\python.exe -m pytest OpenEmotion\\tests\\test_self_model_single_authority.py -q"`
- `python3 -m py_compile OpenEmotion/tools/e2e_self_model_adapter.py OpenEmotion/tests/test_self_model_single_authority.py`
- `python3 scripts/codex/verify_repo.py --mode fast` (archive self-model docs clarification wave)
