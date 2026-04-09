# Repo Authority Cleanup - STATUS

## Current milestone

- name: repo_authority_cleanup: closeout-complete (repo/integration scope)
- owner: Codex
- state: complete

## Current state

- current_layer: repo_authority_cleanup
- repo_authority_cleanup: closeout-complete (repo/integration scope)
- main_chain_status: phase0_truth_map_landed_identity_authority_wave_landed_self_model_authority_wave_landed_milestone2_classification_landed_milestone3_admission_landed_milestone4_proto_self_restore_generated_edge_cleared_proto_self_restore_deleted_self_model_mirror_tool_import_removed_mvp13_report_archive_based_e2e_adapter_report_archive_based_archive_self_model_docs_clarified_oe_mvp13_archive_evidence_only_archive_self_model_body_clarified_archive_self_model_paths_clarified_e2e_adapter_legacy_artifact_dir_clarified_self_model_adapter_core_and_dual_repo_live_callers_removed_mvp13_proof_tests_migrated_to_formal_owner_store_self_model_delete_admission_finished_adapter_mirror_deleted_reflection_legacy_runtime_callers_removed_reflection_probe_archive_only_reflection_trigger_substrate_retained_drives_authority_wave_landed_drive_adapter_and_emotiond_drives_demoted_thin_substrate_retained_developmental_authority_wave_landed_developmental_core_retained_as_active_substrate_clean_clone_ci_final_closeout_proof_passed
- completion_class: complete

## Completed work

- 已创建 long-run task package：`docs/codex/tasks/repo-authority-cleanup/`
- 已确认当前 formal mainline 不变：`native_hooks -> proto_self_runtime -> proto_self_adapter -> proto_self_v2/kernel`
- 已确认 `identity` 代码级单一 authority wave 已落地，并由 single-authority gate 和 identity proof test 共同约束
- 已确认 `self-model` formal owner 当前在主链上被 runtime projection/writeback 消费
- 已确认 `drives` formal owner 当前在主链上被 runtime projection/writeback 消费，`drive_adapter.py` 与 `emotiond/drives/*` 只保留 compat/projection/helper surfaces
- 已确认 `developmental` formal owner 当前在主链上被 runtime projection/writeback 与 v2 developmental bridge 消费，`emotiond/developmental_core/*` 只保留 implementation library 角色，`emotiond/developmental/*` 与 `mvp16` 工具只保留 compat/reference / proof-e2e surface
- 已确认 `proto_self_restore.py` 已物理删除；当前 formal caller 为 0，且 tools/docs/generated caller 已清除；`emotiond/self_model_adapter.py`、`emotiond/self_model_mirror.py` 也已物理删除
- 已完成 Phase 0 六个 ledger 首版落地：`AUTHORITY_MATRIX / CALLER_MATRIX / FILE_FATE_LEDGER / CANONICAL_DOCS_INDEX / ARTIFACT_LOG_INVENTORY / CONFLICT_REGISTER`
- 已完成 `self-model` 代码级 authority 收口：formal owner 自证、legacy adapter/mirror 自降级、single-authority static regression 落地
- 已完成 `identity` 代码级 authority 收口：唯一 live runtime authority 仍在 v1 substrate，reference-only owner surfaces 与 proof test 已对齐
- 已完成 `drives / reflection / developmental` 的 caller/authority ledger 收口，不改语义；developmental 已从 unresolved split 收口为 single authority + implementation library split
- 已完成 clean-clone / CI final closeout proof：在 `Ego-cleancloseout` clean clone 上，`verify_cleanup_admission.py`、`verify_proto_self_single_authority.py`、`verify_repo.py --mode fast`、settled-branch targeted tests、repo-level `git diff --check` 与 clean-clone `git status` 均已通过；targeted tests 期间曾写入 repo-tracked generated residue，后已通过显式 `git restore` / `rm -f` 清理并再次验证 clean 状态
- 已为 clean-clone settled autonomy tests 补上最小 support module `EgoCore/app/autonomy/repository.py` 与 `autonomy_runs` schema bootstrap；该修复只为证明仓库可在 clean clone 中自举完成 settled tests，不改变 formal mainline 或 authority/runtime 语义
- 已移除 `EgoCore/app/openemotion_adapter/__init__.py` 中对 `ProtoSelfRestore` 的 package re-export；当前只剩 docs/generated residue
- 已建立 canonical/archive boundary marker：`docs/canonical/README.md`、`docs/archive/README.md`、`artifacts/current/README.md`、`artifacts/archive/README.md`
- 已建立 canonical/archive/current/archive/generated/dirty-worktree admission boundary：新增 `EgoCore/docs/generated/README.md`、`DIRTY_WORKTREE_BOUNDARY.md`、`CLEAN_CLONE_CLOSEOUT_PROOF.md`，并把 `verify_cleanup_admission.py` 扩展为强制检查这些 admission surfaces
- 已新增 cleanup admission gate：`scripts/codex/verify_cleanup_admission.py`
- 已重新生成 `EgoCore/docs/generated/*`，清除 `proto_self_restore` 的 generated import-map stale edge；随后又完成 file inventory residue 清理，`proto_self_restore` 不再是 blocker
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

- mode: clean-clone / CI final closeout proof
- result: passed
- summary:
  - clean clone path: `/mnt/d/Project/AIProject/MyProject/Ego-cleancloseout`
  - `python3 scripts/codex/verify_cleanup_admission.py` -> passed
  - `python3 scripts/codex/verify_proto_self_single_authority.py` -> passed
  - `python3 scripts/codex/verify_repo.py --mode fast` -> passed
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_autonomy_orchestrator.py EgoCore/tests/test_openemotion_adapter_shims.py EgoCore/tests/test_doc_system_inventory_builder.py -q -s` -> `8 passed`
  - `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego-cleancloseout\OpenEmotion && .venv\Scripts\python.exe -m pytest tests\mvp15 -q"` -> `49 passed`
  - `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego-cleancloseout\OpenEmotion && .venv\Scripts\python.exe -m pytest tests\mvp16 -q"` -> `45 passed`
  - targeted tests dirtied repo-tracked generated residue under `EgoCore/docs/generated/*` and `OpenEmotion/artifacts/mvp12/*`
  - `git restore --worktree --staged EgoCore/docs/generated OpenEmotion/artifacts/mvp12`
  - `git clean -fd OpenEmotion/artifacts/mvp12`
  - `git diff --check` -> passed after explicit cleanup
  - `git status --short --branch` -> clean (`## main...origin/main`) after explicit cleanup
  - `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego\OpenEmotion && set PYTHONPATH=D:\Project\AIProject\MyProject\Ego\OpenEmotion;D:\Project\AIProject\MyProject\Ego\EgoCore;D:\Project\AIProject\MyProject\Ego\EgoCore\modules && .venv\Scripts\python.exe -m pytest tests\test_identity_single_authority.py openemotion\proto_self\tests\test_kernel_identity.py -q"` -> `6 passed`
  - `python3 -m py_compile scripts/codex/verify_proto_self_single_authority.py OpenEmotion/tests/test_identity_single_authority.py`
  - `python3 scripts/codex/verify_proto_self_single_authority.py` -> passed
  - `python3 scripts/codex/verify_repo.py --mode fast` -> passed
  - scoped `git diff --check` -> passed

## Decisions made

- 第一轮 milestone 固定为 `Phase 0 + identity authority wave + self-model authority wave`
- `identity` 本轮已落地为 resolved single runtime authority，只做 ledger/doc/gate 对齐，不重复设计
- `self-model` 本轮采取最小代码收口：formal owner 自证 + legacy adapter/mirror 自降级 + no-dual-authority static assertion
- `drives / reflection / developmental` 第一轮先做 ledger 与 conflict register；其中 drives 这一支已完成 authority wave，reflection 已完成 legacy caller wave，developmental 已完成 authority wave
- `developmental` 本轮后的唯一 runtime authority 固定为 `openemotion.developmental_self/*`；`OpenEmotion/emotiond/developmental_core/*` 继续作为 implementation library，`OpenEmotion/emotiond/developmental/*` 与 `OpenEmotion/tests/mvp16/*` 仅保留 wrapper/reference / proof-e2e 角色
- `identity` 本轮后的唯一 runtime authority 固定为 `openemotion.proto_self.state.IdentityInvariants`；`openemotion.identity.*` 仅保留 reference-only 角色
- `emotiond/self_model_adapter.py` 固定为 `compatibility_only`，`emotiond/self_model_mirror.py` 固定为 `reference_only`
- `drives / reflection / developmental` 本轮只做 caller/authority 定性；drives、reflection、developmental 这三支都已完成各自 authority/caller wave，不再作为 later wave blocker
- `proto_self_restore` 当前已物理删除，且 package re-export / generated import-map / generated file inventory residue 都已清除
- `self_model_mirror` 当前仍有 legacy daemon callers，但 archive report tools 已从 remaining caller lists 中退出；`main_chain_wiring_check.py` / `mvp13_daily_report.py` 不再作为真实 code caller，`OE_MVP:13` 也不再把 adapter 口径写成 current mainline
- `dual_repo_closed_loop_e2e.py` 当前被明确标成 legacy compatibility harness，不再允许被误读为 formal mainline verifier
- `e2e_self_model_adapter.py` 当前被明确标成 archive/reference-only 报告，不再允许被误读为 live adapter exercise harness
- `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 当前不再把 live `emotiond/self_model_adapter.py` 文件路径列为 `OE_MVP:13` evidence
- canonical/docs/artifact 当前只建立 admission boundary，不做物理迁移
- archive self-model 文档当前只保留历史快照表述，不再把旧 wiring 结果写成 current formal mainline
- archive self-model 文档当前也不再把 SelfModelAdapter 报告路径指向非 archive 文档位置
- `e2e_self_model_adapter.py` 当前虽仍读取 `artifacts/self_model_adapter`，但口径已明确为 legacy artifact directory 上的历史归档报告
- clean-clone / CI final closeout proof 已完成；原因是 clean clone `Ego-cleancloseout` 上 `verify_cleanup_admission.py`、`verify_proto_self_single_authority.py`、`verify_repo.py --mode fast`、settled-branch targeted tests、repo-level `git diff --check` 与 clean-clone `git status` 均已通过
- 为修复 clean-clone settled autonomy tests 的缺口，新增 `EgoCore/app/autonomy/repository.py` 并补齐 `autonomy_runs` schema bootstrap；原因是该支持层缺失会让 autonomy settled tests 在 clean clone 中无法落库，但这不改变 formal mainline 或 authority/runtime 语义

## Optional housekeeping / future cleanup backlog

- archive/reference-only docs further compression
- optional physical archive of non-authoritative proof surfaces
- any later non-authoritative generated-residue tidy-up

## Open risks

- worktree 脏文件很多，提交必须极度 scoped
- `proto_self_restore` 当前已无代码 caller，且 generated file inventory residue 已清除，不再是 blocker
- `proto_self_restore.py` 当前已 delete-done，不再报 delete-ready
- reflection legacy runtime caller 已收口，当前只剩 `emotiond/reflection.py` 的 thin trigger/report substrate 与 archive/reference-only probe surface；reflection 本体不再是 delete blocker，但 trigger substrate 是否保留仍待后续 dedicated wave 决定
- developmental caller matrix 已收口，当前不再是 blocker；后续若继续，只会是 `developmental_core` 进一步收缩或 wrapper/reference 物理归档
- archive self-model docs 已完成降噪，当前不再是 blocker
- `self-model` dual-authority 已收口；`self_model_adapter.py` 与 `self_model_mirror.py` 已物理删除，当前不再是 delete-ready blocker
- artifacts/logs 仍未物理迁移；archive/current 目录现在只是 boundary marker，但不再阻塞 clean-clone / CI final closeout proof
- clean-clone proof 的可重复性依赖 explicit generated-residue cleanup；未来重跑时必须在 targeted tests 之后再次执行 restore/remove 再验 clean

## Next step

- 当前下一步：仅保留 `optional housekeeping / future cleanup backlog`，不再继续新的 authority cleanup
- 当前下一步：`delete admission proof and generated/docs cleanup`、`dual_repo_closed_loop_e2e.py`、reflection trigger substrate retirement 等剩余议题都已退回 backlog，不再阻塞本任务 closeout

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
- `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego\OpenEmotion && set PYTHONPATH=D:\Project\AIProject\MyProject\Ego\OpenEmotion;D:\Project\AIProject\MyProject\Ego\EgoCore;D:\Project\AIProject\MyProject\Ego\EgoCore\modules && .venv\Scripts\python.exe -m pytest tests\test_identity_single_authority.py openemotion\proto_self\tests\test_kernel_identity.py -q"`
- `python3 -m py_compile scripts/codex/verify_proto_self_single_authority.py OpenEmotion/tests/test_identity_single_authority.py`
- `python3 scripts/codex/verify_proto_self_single_authority.py`
- `python3 EgoCore/tools/build_doc_system_inventory.py`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_doc_system_inventory_builder.py -q -s`
- `python3 -m py_compile OpenEmotion/tools/mvp13_daily_report.py OpenEmotion/tools/dual_repo_closed_loop_e2e.py OpenEmotion/tests/test_self_model_single_authority.py`
- `cmd.exe /c "OpenEmotion\\.venv\\Scripts\\python.exe -m pytest OpenEmotion\\tests\\test_self_model_single_authority.py -q"`
- `python3 -m py_compile OpenEmotion/tools/e2e_self_model_adapter.py OpenEmotion/tests/test_self_model_single_authority.py`
- `python3 scripts/codex/verify_repo.py --mode fast` (archive self-model docs clarification wave)
- `git clone --branch main git@github.com:pen364692088/EGO.git /mnt/d/Project/AIProject/MyProject/Ego-cleancloseout`
- `python3 scripts/codex/verify_cleanup_admission.py`
- `python3 scripts/codex/verify_proto_self_single_authority.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_autonomy_orchestrator.py EgoCore/tests/test_openemotion_adapter_shims.py EgoCore/tests/test_doc_system_inventory_builder.py -q -s`
- `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego-cleancloseout\OpenEmotion && .venv\Scripts\python.exe -m pytest tests\mvp15 -q"`
- `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego-cleancloseout\OpenEmotion && .venv\Scripts\python.exe -m pytest tests\mvp16 -q"`
- `git restore --worktree --staged EgoCore/docs/generated OpenEmotion/artifacts/mvp12`
- `git clean -fd OpenEmotion/artifacts/mvp12`
- `git diff --check`
- `git status --short --branch`
