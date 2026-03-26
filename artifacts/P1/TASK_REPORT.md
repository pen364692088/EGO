# P1 TASK_REPORT

## 任务名称
P1：RuntimeV2Loop 主链瘦身手术

## 任务类型
架构重构 / 主链瘦身 / 责任切分

## 目标与成功判据
- 把 `RuntimeV2Loop` 从“功能垃圾桶”收回为主流程协调器
- 抽离 Proto-Self ingress、risk signal、evidence capture、external_result feedback
- 保持现有主链可观察行为不主动改变
- 让新边界可单测、可审计

## 当前层级
主链实现层 / 架构收口层

## 当前确定项
- `loop.py` 在重构前同时承担 session orchestration、risk 评估、proto-self event 构造、evidence capture、trace 写入、external_result 回流
- P0 已确认当前最高安全口径仍是 E4 样本级 + E5 准入通过；P1 不得越级报“更稳定”
- adapter 仍应保持薄层，宿主 helper 才是本轮承接点

## 关键未知
- `test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete` 已归因到测试构造的 Windows JSON 路径转义失配；但修完这条后是否还有第二层 runtime 问题，仍未知
- loop 之外的 transition / state / decision 是否还存在第二层职责堆积
- 本轮 helper 形态是否足够支撑 P2，而不再产生新的宿主垃圾桶

## 唯一主执行链
1. 审计 `loop.py` 责任图
2. 抽出纯宿主 helper
3. 收回 `RuntimeV2Loop` 主流程
4. 跑最小回归
5. 记录成功证据和失败样本

## 本次改动
- 新增 `EgoCore/app/runtime_v2/proto_self_runtime.py`
- 将以下职责从 `loop.py` 内联逻辑拆出：
  - `assess_risk_level`
  - `build_proto_self_ingress_event`
  - `build_external_result_event`
  - `RuntimeV2ProtoSelfRuntime.process_ingress`
  - `RuntimeV2ProtoSelfRuntime.process_external_result`
  - `RuntimeV2ProtoSelfRuntime.capture_response_plan`
- 保留 `loop._assess_risk_level()` 作为兼容包装，避免旧脚本直接失效
- 新增 `EgoCore/tests/test_runtime_v2_proto_self_runtime.py`

## 责任边界变化
- `RuntimeV2Loop`：保留 turn orchestration、state mutation、decision loop、transition apply、最终 result 返回
- `proto_self_runtime.py`：承接 Proto-Self ingress / feedback / evidence / trace side-effects
- `telegram_evidence_collector.py`：继续负责证据落盘，不上升为 orchestration owner

## 验证结果
- `python3 -m py_compile EgoCore/app/runtime_v2/loop.py EgoCore/app/runtime_v2/proto_self_runtime.py EgoCore/tests/test_runtime_v2_proto_self_runtime.py`：通过
- `cmd.exe /c py -3 -m pytest tests\\test_runtime_v2_proto_self_runtime.py tests\\test_runtime_v2_turn_result.py -q`：`7 passed`
- `cmd.exe /c py -3 -m pytest tests\\test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete tests\\test_runtime_v2_proto_self_runtime.py tests\\test_runtime_v2_turn_result.py -q`：`8 passed`
- 历史失败样本 `tests/test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete` 已归因为测试契约失配并修复
- 失败归因与修复见：`artifacts/P1/FAILURE_ATTRIBUTION.md`
- 结构量化：`loop.py` 从 `376` 行降到 `259` 行；proto-self 相关宿主职责迁移到 `proto_self_runtime.py`

## 行为保持说明
- 本轮没有主动改 `run_turn_typed()` 的对外签名
- 没有把 Proto-Self 逻辑平移进 adapter
- 没有改 Telegram / integration / simulated 的 runner 接口
- 当前已修复 1 条由测试契约失配造成的最小回归；因此本轮可安全表述为“主链瘦身完成，且当前已验证的最小回归恢复通过”

## 本次结论能证明什么
- 能证明 `RuntimeV2Loop` 已显著瘦身，内联职责已拆到宿主 helper
- 能证明 proto-self ingress / feedback / evidence capture 的结构化边界比重构前更清晰
- 能证明新增 helper 的关键数据形状已被单测约束
- 能证明先前那条最小回归的首要问题属于测试 JSON 构造失配，而非已证实的 P1 主链语义回归

## 本次结论不能证明什么
- 不能证明 runtime 全量回归已全部通过
- 不能证明真实 Telegram / integration / simulated 可观察行为完全未变
- 不能证明系统更稳定
- 不能证明 P2 已可无风险展开

## 离 P2 还差什么
- 需要确认 `loop.py` 之外的 state / transition / decision 还剩多少跨层状态语义
- 需要把本轮 helper 的“临时宿主归属”在 P2 前进一步固定，避免再次堆积
