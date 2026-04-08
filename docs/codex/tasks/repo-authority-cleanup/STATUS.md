# Repo Authority Cleanup - STATUS

## Current milestone

- name: Milestone 4 - Delete Admission Proof and Generated/Docs Cleanup
- owner: Codex
- state: in_progress

## Current state

- current_layer: repo_authority_cleanup
- main_chain_status: phase0_truth_map_landed_identity_baseline_confirmed_self_model_authority_wave_landed_milestone2_classification_landed_milestone3_admission_landed_milestone4_proto_self_restore_generated_edge_cleared_self_model_mirror_tool_import_removed
- completion_class: conditional_complete

## Completed work

- 已创建 long-run task package：`docs/codex/tasks/repo-authority-cleanup/`
- 已确认当前 formal mainline 不变：`native_hooks -> proto_self_runtime -> proto_self_adapter -> proto_self_v2/kernel`
- 已确认 `identity` 代码级单一 authority baseline 已存在，可直接作为本轮基线复核
- 已确认 `self-model` formal owner 当前在主链上被 runtime projection/writeback 消费
- 已确认 `emotiond/self_model_adapter.py`、`emotiond/self_model_mirror.py`、`proto_self_restore.py` 当前 formal caller 为 0，但仍存在 tools/docs/generated caller
- 已完成 Phase 0 六个 ledger 首版落地：`AUTHORITY_MATRIX / CALLER_MATRIX / FILE_FATE_LEDGER / CANONICAL_DOCS_INDEX / ARTIFACT_LOG_INVENTORY / CONFLICT_REGISTER`
- 已完成 `self-model` 代码级 authority 收口：formal owner 自证、legacy adapter/mirror 自降级、single-authority static regression 落地
- 已完成 `drives / reflection / developmental` 的 caller/authority ledger 收口，不改语义
- 已移除 `EgoCore/app/openemotion_adapter/__init__.py` 中对 `ProtoSelfRestore` 的 package re-export；当前只剩 docs/generated residue
- 已建立 canonical/archive boundary marker：`docs/canonical/README.md`、`docs/archive/README.md`、`artifacts/current/README.md`、`artifacts/archive/README.md`
- 已新增 cleanup admission gate：`scripts/codex/verify_cleanup_admission.py`
- 已重新生成 `EgoCore/docs/generated/*`，清除 `proto_self_restore` 的 generated import-map stale edge；当前剩余 residue 为 generated file inventory 与 compat/historical docs
- 已移除 `OpenEmotion/tools/main_chain_wiring_check.py` 对 `emotiond.self_model_mirror` 的真实 import，并把 `OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml` 的 `OE_MVP:13` 证据改成历史 shadow 口径

## Last validation results

- mode: milestone-4 scoped verification
- result: passed
- summary:
  - `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion python3 -m pytest EgoCore/tests/test_doc_system_inventory_builder.py -q -s` -> `1 passed`
  - regenerated `EgoCore/docs/generated/import_or_reference_map.csv` no longer contains stale `__init__.py -> proto_self_restore` edge
  - `python3 scripts/codex/verify_repo.py --mode fast` -> passed
  - scoped `git diff --check` passed on touched non-generated files

## Decisions made

- 第一轮 milestone 固定为 `Phase 0 + identity baseline closeout + self-model authority wave`
- `identity` 本轮不重复设计，只做 ledger/doc/gate 对齐
- `self-model` 本轮采取最小代码收口：formal owner 自证 + legacy adapter/mirror 自降级 + no-dual-authority static assertion
- `drives / reflection / developmental` 第一轮只进 ledger 与 conflict register，不进语义改造
- `self-model` 本轮后的唯一 authority 固定为 `openemotion.self_model/*`；`openemotion.proto_self.self_model` 仅保留 active compute/proposal substrate 角色
- `emotiond/self_model_adapter.py` 固定为 `compatibility_only`，`emotiond/self_model_mirror.py` 固定为 `reference_only`
- `drives / reflection / developmental` 本轮只做 caller/authority 定性，不改 owner/substrate 语义
- `proto_self_restore` 当前 formal caller 仍为 0，且 package re-export 已被清除；删除 admission 现在只剩 docs/generated residue
- `proto_self_restore` 当前 formal caller 仍为 0，package re-export 与 generated import-map stale edge都已清除；删除 admission 现在只剩 generated file inventory 与 compat/historical docs residue
- `self_model_mirror` 当前仍有 legacy daemon/tool callers，但 `main_chain_wiring_check.py` 不再作为真实 code caller；`OE_MVP:13` 也不再把 adapter 口径写成 current mainline
- canonical/docs/artifact 当前只建立 admission boundary，不做物理迁移

## Open risks

- worktree 脏文件很多，提交必须极度 scoped
- `proto_self_restore` 当前虽已无代码 caller，但 generated file inventory 与 compat/historical docs residue 仍在，不能直接删
- `self_model_adapter / self_model_mirror` 当前仍不能删；`emotiond/core.py` 与 legacy tools callers 仍在
- `self-model` dual-authority 已收口，但 legacy adapter/mirror 仍有 tool/docs caller，当前还不能删
- reflection legacy residue 仍有 `emotiond/core.py` caller；当前只能维持 `reference_only`
- artifacts/logs 仍未物理迁移；archive/current 目录现在只是 boundary marker

## Next step

- 当前下一步：继续做 `delete admission proof and generated/docs cleanup`，优先收窄 `proto_self_restore` 的 inventory/docs callers，再处理 `self_model_adapter / self_model_mirror` 的 tool/docs callers；`drives / reflection / developmental` 仍不改语义
- 当前下一步：继续做 `delete admission proof and generated/docs cleanup`，优先收窄 `self_model_adapter / self_model_mirror` 的剩余 legacy tool/docs callers；`drives / reflection / developmental` 仍不改语义

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
