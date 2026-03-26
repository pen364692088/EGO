# P5 FAILURE_SAMPLES

| failure_id | evidence_level | source_type | artifact_path | failure | status |
|---|---|---|---|---|---|
| P5-F-001 | E1 | code audit | [`EgoCore/app/runtime_v2/loop.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/runtime_v2/loop.py#L1) | 主链 runtime 曾在模块开头手动插入 sibling `OpenEmotion` 路径 | 已修正 |
| P5-F-002 | E1 | code audit | [`EgoCore/app/main.py`](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/app/main.py#L1) | 正式入口曾把工程边界问题伪装成运行时 path hack | 已修正 |
| P5-F-003 | E1 | code audit | [`OpenEmotion/pyproject.toml`](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/pyproject.toml#L24) | 正式包配置曾未包含 `openemotion*`，导致主链 import 主要依赖源码路径 | 已修正 |
| P5-F-004 | E1 | environment | `python3 -m venv /tmp/p5_linux_venv` 本轮输出 | Linux 容器缺少 `ensurepip` / `python3-venv`，无法做隔离 editable-install 验证 | 保留为环境阻塞，不归因于代码本体 |
