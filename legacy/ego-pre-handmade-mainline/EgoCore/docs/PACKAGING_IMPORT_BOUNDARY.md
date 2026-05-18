# Packaging / Import Boundary

## Authority
- 正式导入方式的权威源是工程配置：`EgoCore/pyproject.toml` 与 `OpenEmotion/pyproject.toml`
- 运行时业务模块不再负责修改 `sys.path`

## 开发态（monorepo）
从仓库根目录执行：

```bash
python -m pip install -e OpenEmotion
python -m pip install -e EgoCore
```

然后可从任意工作目录使用：

```bash
python -m app.main --status
python -m app.main --telegram
python -m pytest EgoCore/tests/test_packaging_import_boundaries.py -q
```

## subtree / 单仓场景
- 如果只带 `EgoCore`，则需要预先安装 `openemotion` 包
- 如果只带 `OpenEmotion`，则它自身可以独立作为 `openemotion` / `emotiond` 包安装

## CI 建议
```bash
python -m pip install -e OpenEmotion
python -m pip install -e EgoCore[dev]
python -m pytest EgoCore/tests/test_packaging_import_boundaries.py -q
python -m pytest EgoCore/tests/test_runtime_v2_proto_self_runtime.py -q
```

## 兼容保留
- 历史 `tools/`、`scripts/`、部分旧 `tests/` 里仍有 path hack
- 这些不再是正式导入权威源，后续按兼容清单逐步退出
