# 06_AGENT_ONBOARDING.md

## 欢迎

你是新加入的 agent，负责 OpenEmotion 主体内核的开发和维护。

## 第一步：理解边界

**最重要**：理解 OpenEmotion 和 EgoCore 的边界。

- OpenEmotion 负责主体本体
- EgoCore 负责运行时和工具执行
- 不允许双主

阅读顺序：
1. `docs/03_BOUNDARY_AND_OWNERSHIP.md`
2. `POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md`

## 第二步：理解当前主线

当前主线是 **Proto-Self Kernel v1**。

阅读顺序：
1. `docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
2. `docs/PROTO_SELF_KERNEL_V1_SPEC.md`
3. `openemotion/proto_self/kernel.py` — 主循环实现

核心概念：
- `process_event(state, event) → KernelOutput`
- 4+1 状态：identity_invariants, self_model, drive_field, cycle_store, episodic_trace
- 事件进入 → 内态更新 → 倾向生成 → 后果回流

## 第三步：理解验证状态

阅读 `docs/PROGRAM_STATE_UNIFIED.yaml`：
- 查看当前验证状态
- 理解 verified_e2e / verified_acceptance / verified_mainline_e2e 的含义

当前状态：
- PROTO_SELF_KERNEL_V1: verified_mainline_e2e
- CYCLE_CORE_V1: verified_e2e
- WS_C1: verified_e2e

## 第四步：理解改功能流程

阅读 `docs/04_CHANGE_ROUTING.md`：
- 先判断归属（OpenEmotion 还是 EgoCore）
- 再找到对应目录和文件
- 涉及双核接口时必须联动看

## 第五步：理解记忆系统

阅读：
1. `docs/MEMORY_MODEL_V1.md`
2. `openemotion/memory/`

三层记忆：
- event_memory（不可变）
- narrative_memory（可变）
- policy_memory（生命周期）

## 常见任务

### 任务 A：添加新的 drive_field 变量
1. 先在 `openemotion/proto_self/state.py` 的 `DriveField` 添加字段
2. 在 `openemotion/proto_self/appraisal.py` 的 `update_drive_field()` 添加计算逻辑
3. 添加单元测试验证对 policy_hint 的影响

### 任务 B：添加新的 reflection 触发条件
1. 先在 `openemotion/proto_self/reflection.py` 的 `maybe_reflect()` 添加条件
2. 添加单元测试验证触发逻辑
3. 确保 reflection_note 不包含直接执行命令

### 任务 C：修改 KernelEvent 字段
1. 先更新 `openemotion/proto_self/schemas.py`
2. 更新 EgoCore `app/openemotion_adapter/proto_self_adapter.py` 的 normalize 逻辑
3. 添加 schema 版本检查

## 禁止事项

1. ❌ 在 EgoCore 中实现主体语义
2. ❌ 在 OpenEmotion 中直接执行工具
3. ❌ 跳过 schema 直接改字段
4. ❌ 输出包含直接执行命令

## 提交规范

- 单元测试必须通过
- 边界检查必须通过
- 涉及双核接口时必须联动更新
