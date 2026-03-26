# PROJECT_MEMORY.md

> AIProject 核心记忆 - Claude Code 持续更新
> 最后更新: 2026-03-25

---

## 项目概览

| 项目 | 值 |
|------|------|
| 名称 | EGO - AI Agent Monorepo |
| 架构 | EgoCore (宿主) + OpenEmotion (主体内核) 分层设计 |
| 路径 | `D:\Project\AIProject\MyProject\Ego` |
| 子仓库 | EgoCore, OpenEmotion (subtree 集成) |

---

## 核心协议

- **元认知内核**: 每轮明确目标→审查模型→定位未知→推进闭环
- **硬性门槛**: 语义未定义不实现，无验证证据不宣称完成
- **层级模型**: 目标→策略→表示→实现→验证→收口
- **效果优先**: 终点是"接入主流程并生效"，而非"模块完成"
- **表示优先**: 先判断信息表示是否正确，再改实现

---

## 系统边界

| 组件 | 职责 |
|------|------|
| **EgoCore** | 外部交互、runtime、工具执行、治理壳、现实裁决 |
| **OpenEmotion** | self-model、memory evolution、appraisal、reflection |

**边界规则**:
- 不让 EgoCore 偷做 OpenEmotion 本体
- 不让 OpenEmotion 偷做现实执行与运行时治理

---

## 工作偏好

### 任务模板
- 强制使用 `Tasks/templates/` 中的模板
- 选择: quick_fix → functional → dual_repo/boundary_fix

### Git 工作流
- **pen364692088 仓库**: commit 后自动推送
- **其他仓库**: 等待用户确认后推送

### E2E 测试流程
1. 停止现有 EgoCore 进程
2. 清理 state mirror/trace (如需隔离)
3. 启动: `python -m app.main --telegram`
4. 等待就绪 → 执行测试 → 收集 artifacts

---

## 已验证的关键发现

| 发现 | 详情 |
|------|------|
| Proto-Self 配置陷阱 | `openemotion.enabled` 默认为 false |
| 误聚合根因 | `psi_bucket` 不含 `safety_context.risk` |
| Runtime 数据流陷阱 | `runtime_v2/loop.py` 不能硬编码 `safety_context: {}` |
| 字段名一致性 | OpenEmotion 期望 `risk`，EgoCore 使用 `risk_level` |
| 关键词优先级 | service_control/test_verify 需提前匹配 |
| 传输层边界 | simulated / integration / real_channel 应复用同一条 runtime 主链，只替换 ingress/egress 证据来源 |
| E4 最小证据包 | E4 样本除 raw/update/event/result/plan/outbox 外，还需 timeline + tape + replay artifact |
| 环境执行口径 | 当前工作区内 E2/E3 runner 以 Windows `py -3` 实跑通过；Linux `python3` 仅适合静态检查，依赖不完整 |
| E5 准入门槛 | 进入观察期前，至少要有 1 个完整普通 real 样本 + 1 个完整且命中高风险路径的 real 样本 |

---

## 关键代码路径

| 功能 | 文件 |
|------|------|
| Cycle 聚合 | `OpenEmotion/openemotion/proto_self/cycles.py` |
| Risk 字段映射 | `EgoCore/app/openemotion_adapter/event_builder.py` |
| Runtime 风险传递 | `EgoCore/app/runtime_v2/loop.py` |
| 诊断脚本 | `OpenEmotion/scripts/proto_self_diagnostics.py` |
| 统一 runner | `scripts/telegram_mainline_common.py` |
| E4 报告生成 | `scripts/run_telegram_real_channel_capture.py` |

---

## 里程碑

| 日期 | 里程碑 |
|------|--------|
| 2026-03-24 | Proto-Self Kernel v1 验证 - 6 Gate 全部通过 |
| 2026-03-24 | EgoCore Parser 主链收口 - 45 单元 + 8 E2E 通过 |
| 2026-03-25 | EGO 总仓 + Subtree 集成链生效 |
| 2026-03-25 | P0-R3 runtime 主链接线修复完成 |
| 2026-03-25 | simulated / integration / real_channel runner 对齐为同一 runtime 主链，E4 replay artifact 补齐 |
| 2026-03-25 | unified runner 跨层一致性实跑通过：E2/E3 共用 `RuntimeV2Loop`，E4 参考样本形成对照证据 |
| 2026-03-25 | E4→E5 准入未通过：当前缺少已验证命中高风险路径的完整真实样本 |
| 2026-03-25 | 高风险真实样本 `sample_20260325_200847_4d2b5dae` 采集完成，`risk = high`，E4→E5 准入复判通过 |

---

## 待办/待观察

- [ ] 持续更新此文件

---

*此文件由 Claude Code 动态维护，记录项目核心记忆*
