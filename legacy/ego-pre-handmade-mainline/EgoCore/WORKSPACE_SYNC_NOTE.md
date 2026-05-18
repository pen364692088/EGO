# Workspace 同步注意事项

## 项目仓库位置

**正确位置**: `/home/moonlight/Project/Github/MyProject/EgoCore`

**不要提交到**: `~/.openclaw/workspace/` (这是 OpenClaw 运行时目录)

## 文件映射关系

| Workspace 路径 | EgoCore 路径 | 说明 |
|---------------|-------------|------|
| `~/.openclaw/workspace/docs/` | `EgoCore/docs/` | 文档 |
| `~/.openclaw/workspace/templates/` | `EgoCore/templates/` | 模板 |
| `~/.openclaw/workspace/tools/` | `EgoCore/tools/` | 工具 |
| `~/.openclaw/workspace/modules/` | `EgoCore/modules/` | 模块实现 |
| `~/.openclaw/workspace/tests/modules/` | `EgoCore/tests/modules/` | 模块测试 |
| `~/.openclaw/workspace/tests/integration/` | `EgoCore/tests/integration/` | 集成测试 |
| `~/.openclaw/workspace/artifacts/integration/` | `EgoCore/artifacts/integration/` | 集成设计 |
| `~/.openclaw/workspace/artifacts/verification/` | `EgoCore/artifacts/verification/` | 验证报告 |

## 同步命令

```bash
# 从 workspace 复制到 EgoCore
cp -r ~/.openclaw/workspace/modules/* /home/moonlight/Project/Github/MyProject/EgoCore/modules/
cp -r ~/.openclaw/workspace/tests/modules/* /home/moonlight/Project/Github/MyProject/EgoCore/tests/modules/
cp -r ~/.openclaw/workspace/tests/integration/* /home/moonlight/Project/Github/MyProject/EgoCore/tests/integration/

# 提交到 EgoCore
cd /home/moonlight/Project/Github/MyProject/EgoCore
git add -A
git commit -m "..."
git push origin main
```

## 测试验证

```bash
cd /home/moonlight/Project/Github/MyProject/EgoCore

# 运行模块测试
python -m pytest modules/runtime_metrics_aggregator/tests/ -v

# 运行集成测试
python -m pytest tests/integration/ -v

# 运行预检工具
python tools/module_preflight_check.py --module runtime_metrics_aggregator --path modules/runtime_metrics_aggregator
```

## 已同步内容 (2026-03-14)

- ✅ `docs/MODULE_DEVELOPMENT_STANDARD.md`
- ✅ `templates/` (3 个模板文件)
- ✅ `tools/module_preflight_check.py`
- ✅ `modules/emotion_context_formatter/` (完整模块)
- ✅ `modules/runtime_metrics_aggregator/` (完整模块)
- ✅ `tests/modules/` (4 个测试文件)
- ✅ `tests/integration/` (4 个集成测试文件)
- ✅ `artifacts/integration/RUNTIME_METRICS_AGGREGATOR_INTEGRATION_PLAN.md`
- ✅ `artifacts/verification/` (4 个验证报告)

## 测试状态

- runtime_metrics_aggregator: **53/53 通过** ✅
- emotion_context_formatter: **50/50 通过** ✅
