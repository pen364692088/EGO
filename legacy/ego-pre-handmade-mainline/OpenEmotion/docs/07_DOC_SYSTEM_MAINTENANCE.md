# 07_DOC_SYSTEM_MAINTENANCE.md

## 目标

把文档系统从"一次性整理"变成"可持续更新的机制"。

## 文档结构

```
docs/
├── 00_MASTER_INDEX.md          # 入口索引
├── 01_PROJECT_OVERVIEW.md      # 项目概览
├── 02_SYSTEM_FLOW.md           # 系统流程（可选）
├── 03_BOUNDARY_AND_OWNERSHIP.md # 边界定义
├── 04_CHANGE_ROUTING.md        # 改功能路由
├── 05_DEPRECATED_AND_SHIMS.md  # 废弃/过渡（待创建）
├── 06_AGENT_ONBOARDING.md      # 新 agent 上手
├── 07_DOC_SYSTEM_MAINTENANCE.md # 本文档
├── PROGRAM_STATE_UNIFIED.yaml  # 权威状态源
├── generated/                  # 自动生成的盘点层
│   ├── module_map.md
│   └── repo_inventory.md
├── PROTO_SELF_KERNEL_V1_DESIGN.md  # 设计稿
├── PROTO_SELF_KERNEL_V1_SPEC.md    # 接口草案
├── MEMORY_MODEL_V1.md              # 记忆模型
└── archive/                        # 归档文档
```

## 什么时候必须更新

以下情况至少要重跑一次盘点：
- 目录结构发生变化
- 新增/删除关键模块
- Proto-Self Kernel 相关文件变化
- deprecated / shim / mirror / cache 状态变化
- 做完一轮较大的架构改动后

## 更新步骤

### Step 1: 重新生成盘点层
```bash
python tools/build_doc_inventory.py
```

### Step 2: 检查 generated 输出
重点看：
- `docs/generated/module_map.md`
- `docs/generated/repo_inventory.md`

### Step 3: 同步人工文档
至少检查并视情况更新：
- `docs/04_CHANGE_ROUTING.md`
- `docs/PROGRAM_STATE_UNIFIED.yaml`
- `README.md`

### Step 4: 若边界受影响
同时检查：
- `docs/03_BOUNDARY_AND_OWNERSHIP.md`
- EgoCore 对应 adapter 文档

## 最小维护原则

每轮大改后，至少完成两件事：
1. 更新 `PROGRAM_STATE_UNIFIED.yaml`
2. 重新检查 `04_CHANGE_ROUTING.md`

## 建议提交方式

如果只是盘点层更新：
- `docs(doc-system): refresh generated inventory`

如果盘点 + 路由/状态一起更新：
- `docs(doc-system): refresh routing and PROGRAM_STATE`
