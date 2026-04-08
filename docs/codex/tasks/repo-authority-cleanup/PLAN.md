# Repo Authority Cleanup - PLAN

## Task summary

把全仓收成“一个正式主链 + 一组单一 authority + 一套 canonical docs + 一条 archive 边界”。当前第一轮只做 `Phase 0 truth map + identity baseline closeout + self-model authority wave（风险可控时） + obvious delete-candidate ledger admission`。

## Milestones

### Milestone 1: Phase 0 Truth Map + Identity Baseline + Self-Model Wave

- scope:
  - 建立 long-run task package 与 6 个 ledger
  - 盘点 formal mainline、authority/substrate、compat/shim/mirror/reference/archive/delete-candidate
  - 复核 `identity` 已落地的单一 runtime authority 基线
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
  - `identity` baseline 与 single-authority docs/gate 对齐
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
  - 若 self-model 波触发 stop 条件，则回退到仅保留 Phase 0 + identity baseline ledger，不带 self-model 代码改动进入提交

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
  - 只做 delete admission proof，不做大规模物理删除
- acceptance:
  - 至少一个 delete-candidate 的非 formal caller 进一步收窄
  - 不引入 formal mainline 回退
- validation:
  - scoped tests
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 generated/docs/tool caller 迁移不清晰，则只更新 ledger，不删文件

## Progress

- current_status: in_progress
- current_milestone: Milestone 4 - Delete Admission Proof and Generated/Docs Cleanup
- milestone_state: executing

## Decision log

- 2026-04-08: 本任务按 long-run cleanup program 执行，不做一次性大删库；原因是 formal mainline 与 current evidence chain 不能被清理动作打断
- 2026-04-08: 第一轮固定只做 `Phase 0 + identity baseline closeout + self-model authority wave`；原因是 drives/reflection/developmental 仍有更高 dual-layer 风险，不能一轮混改
- 2026-04-08: `identity` 不再重复设计；当前已落地代码波次作为 baseline 复核与 ledger 对齐对象
- 2026-04-08: docs/artifacts 先做索引与 fate ledger，不先做物理迁移；原因是当前 scripts/gates/artifacts caller 仍分散
- 2026-04-08: `proto_self_restore` 的 package re-export 可以安全移除；原因是全仓 caller 证明已显示代码 caller 只剩 `__init__.py` 自身，formal mainline 为 0
- 2026-04-08: canonical/docs/artifact 先建立 boundary marker 和 gate，不做物理迁移；原因是当前 docs/scripts/artifacts 仍存在大量路径引用，先锁 admission 比盲目搬迁更安全
- 2026-04-08: `proto_self_restore` 的 generated import-map stale edge 已通过重新生成 inventory 清除；原因是 package re-export 移除后，继续保留旧 generated caller 会误导 delete admission 结论

## Surprises / discoveries

- 当前 worktree 已存在大量与本任务无关的脏文件；提交时必须严格 scoped
- `self-model` legacy adapter/mirror 当前 formal caller 为 0，但仍有 tools/docs/generated caller
- `proto_self_restore.py` formal caller 为 0，但 `EgoCore/app/openemotion_adapter/__init__.py` 仍 re-export 它，删除 admission 不能直接跳过
- `proto_self_restore.py` 当前仍不能删；虽然 package re-export 和 generated import-map stale edge 已清掉，但 generated file inventory 与 compat/historical docs residue 还在

## Outcomes / retrospective

- 本轮已证明：
  - `identity` baseline 已在代码级收口，可直接作为 Phase 0 基线
  - `self-model` formal owner 已在 current mainline 上被 runtime 注入与 writeback 消费；legacy adapter/mirror 不在 formal caller 上
- 还没证明：
  - `proto_self_restore` 是否已可直接删除
  - drives/reflection/developmental 的删除 admission 还不清楚
- 下一步最小闭环动作：
  - 继续收窄 `proto_self_restore` 的 inventory/docs residue
  - 再进入 `self_model_adapter / self_model_mirror` 的 tool/docs caller 收窄
