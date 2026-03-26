# P5 EVIDENCE_TABLE

| evidence_id | evidence_level | source_type | artifact_path | what_it_proves | what_it_does_not_prove |
|---|---|---|---|---|---|
| P5-E-001 | E1 | code config | [`EgoCore/pyproject.toml`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/pyproject.toml#L1) | EgoCore 现在有正式 package 配置，并声明 `app / egocore / system_core / runtime_metrics_aggregator / emotion_context_formatter` | 不证明发布到 PyPI 流程已完成 |
| P5-E-002 | E1 | code config | [`OpenEmotion/pyproject.toml`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/pyproject.toml#L24) | OpenEmotion 正式 package 配置不再遗漏 `openemotion*` | 不证明所有 OpenEmotion 历史子包都已独立治理 |
| P5-E-003 | E1 | code audit | [`EgoCore/app/main.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/main.py#L1) | 正式入口已不再运行时改写 `sys.path` | 不证明旧脚本入口已全部迁移 |
| P5-E-004 | E1 | code audit | [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L1) | RuntimeV2Loop 已停止 sibling path hack | 不证明所有 runtime 辅助模块都零 hack |
| P5-E-005 | E1 | code audit | [`EgoCore/system_core/metrics_hook.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/system_core/metrics_hook.py#L1) | `modules/` 主链依赖已改为正式包导入，不再靠路径注入 | 不证明 modules 历史测试入口已统一 |
| P5-E-006 | E1 | code audit | [`EgoCore/app/__init__.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/__init__.py#L1) | `app` 包已改为 lazy export，减少导入副作用和环境脆弱性 | 不证明每个子包都已做同等级懒加载 |
| P5-E-007 | E2 | test | [`EgoCore/tests/test_packaging_import_boundaries.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/tests/test_packaging_import_boundaries.py#L9) | 已有守护测试卡住 package 声明和主链禁用 `sys.path` 注入 | 不证明全仓历史 hack 不再新增 |
| P5-E-008 | E2 | validation | `cmd.exe /c "py -3 -m pytest tests\\test_packaging_import_boundaries.py tests\\test_runtime_v2_proto_self_runtime.py -q"` | Windows 本地最小验证 `10 passed` | 不证明 Linux / CI 都已实跑 |
| P5-E-009 | E1 | doc | [`EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/docs/PACKAGING_IMPORT_BOUNDARY.md#L1) | 已明确 monorepo / subtree / CI 的正式 bootstrap 规则 | 不证明所有开发者都已迁移到新流程 |
