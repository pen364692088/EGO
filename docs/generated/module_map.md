# Module Map

Generated: 2026-03-23T17:29:38.894098

## openemotion/ 目录结构

| 模块 | 文件数 | 说明 |
|------|--------|------|
| [contracts](openemotion\contracts) | 3 | 契约定义 |
| [cycle_core](openemotion\cycle_core) | 5 | Cycle 核心 |
| [identity](openemotion\identity) | 3 | 身份不变量 |
| [interaction](openemotion\interaction) | 3 | 交互层 |
| [memory](openemotion\memory) | 6 | 三层记忆模型 |
| [proto_self](openemotion\proto_self) | 11 | Proto-Self Kernel v1（主体内核主链） |
| [self_model](openemotion\self_model) | 2 | 自我模型 |

## 关键入口文件

| 文件 | 职责 |
|------|------|
| `proto_self/kernel.py` | 主循环 process_event() |
| `proto_self/schemas.py` | KernelEvent / KernelOutput |
| `proto_self/state.py` | ProtoSelfState (4+1 状态) |
| `proto_self/appraisal.py` | drive_field 更新 |
| `proto_self/reflection.py` | 反思触发 |
| `proto_self/cycles.py` | cycle 固化 |
