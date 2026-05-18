# 07_DOC_SYSTEM_MAINTENANCE.md

## 目标

把文档系统从“一次性整理”变成“可持续更新的机制”。

## 重点先看

### 1. generated 文件在哪里
都在：
- `docs/generated/`

包括：
- `repo_inventory.md`
- `file_inventory.csv`
- `module_map.md`
- `import_or_reference_map.csv`
- `orphan_candidates.md`
- `recent_hotspots.md`

### 2. 用哪个脚本更新
统一使用：
- `tools/build_doc_system_inventory.py`

### 3. 什么时候必须更新
以下情况至少要重跑一次：
- 目录结构发生变化
- 新增/删除关键模块
- 兼容路径被降权或移除
- 变更路由文档明显过期
- deprecated / shim / mirror / cache 状态变化
- 做完一轮较大的架构改动后

## 更新步骤（强制建议）

### Step 1: 重新生成盘点层
```bash
python tools/build_doc_system_inventory.py
```

### Step 2: 检查 generated 输出
重点看：
- `docs/generated/recent_hotspots.md`
- `docs/generated/orphan_candidates.md`
- `docs/generated/module_map.md`

### Step 3: 同步人工文档
至少检查并视情况更新：
- `docs/04_CHANGE_ROUTING.md`
- `docs/05_DEPRECATED_AND_SHIMS.md`
- `docs/06_AGENT_ONBOARDING.md`
- `docs/DOC_SYSTEM_BUILD_REPORT.md`

### Step 4: 若边界受影响
同时检查：
- `docs/03_BOUNDARY_AND_OWNERSHIP.md`
- 双仓 contract / adapter / schema 文档

## 重点提醒

- generated 层是**事实盘点层**，不是最终解释层
- `orphan_candidates.md` 不等于可删清单
- 未确认项只能标 candidate，不能直接宣告废弃
- 更新 generated 后，不同步 `04_CHANGE_ROUTING.md` / `05_DEPRECATED_AND_SHIMS.md`，文档系统仍会漂

## 最小维护原则

每轮大改后，至少完成两件事：
1. 重跑 `tools/build_doc_system_inventory.py`
2. 重新检查 `04_CHANGE_ROUTING.md` 和 `05_DEPRECATED_AND_SHIMS.md`

## 建议提交方式

如果只是盘点层更新，建议 commit message 类似：
- `docs(doc-system): refresh generated inventory`

如果盘点 + 路由/废弃表一起更新，建议类似：
- `docs(doc-system): refresh routing and inventory`
