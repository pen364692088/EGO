# WP1 Readiness Report

> authority: `Tasks/MVS_task_plan.md`
> scope: `WP1 宿主壳收稳（MVP11.5）`
> date: 2026-04-01
> status: `not_ready`

## 总结

`WP1` 当前不是方向错误，而是 **已部分生效但尚未 ready**。

- 可以确认的:
  - host-chain 若干关键切片已到 E4
  - `chat_mainline` / `evidence_mainline` / `status_mainline` 已开始分离
  - `ResponsePlan` 已成为正式宿主表达合同骨架
  - `memory_claim_gate` 已拿到 Telegram 真实样本级证据
  - 最小 host-side intent gate 已拿到 Telegram 真实样本级证据
- 还不能确认的:
  - `numeric_leak = 0` 已稳定成立
  - `self_report_contract / SRAP` 已达到可结束 shadow 观察期的 readiness
  - 当前 shadow 观察窗是否足够干净，能直接用于 readiness 裁决

## Readiness 分项

| 项目 | 当前结论 | 证据等级 | 说明 |
|------|----------|----------|------|
| `InteractionKind` / `normalize_user_turn` 作为宿主入口 authority | 已接入 | E3 | 已有代码与回归，但本报告不把它单独升级为 E4 |
| `reply_authority / reply_origin` 正式分层 | 已接入且有真实样本 | E4 | Telegram 真实样本已证明 `model_chat` 与 `host_evidence` 可在同一 session 分离 |
| `chat_mainline` 脱离 execution JSON 主链 | 已接入且有真实样本 | E4 | 普通聊天已由 `llm.use_cases.chat` 驱动 |
| `tools.delivery_bridge` | 已接入且有真实样本 | E4 | evidence delivery 已可审计 |
| `ResponsePlan` 为唯一宿主表达主合同 | 已接入且有真实样本 | E4 | 核心字段已并入，且最小 host-side intent gate 已在 Telegram 真链路触发 |
| `memory_claim_gate` | 已接入且有真实样本 | E4 | Telegram 真实样本已证明：无 restore authority 时不会对外声称“已恢复/记得你”，且聊天不再退化成固定 fallback |
| `self_report_contract / SRAP` 约束并入 `ResponsePlan` | 部分完成 | E4 | 已形成 [WP1_SRAP_MAPPING.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/krd_mvs_mainline/WP1_SRAP_MAPPING.md)，且最小 host-side gate 与 intent source 都已拿到 Telegram E4 |
| `numeric_leak = 0` | 未成立 | E3/E4 混合 | fresh 7d/1d shadow 报告分别给出 `16.06%` / `24.55%`；但同一观测窗被大量 synthetic/test 流量污染，当前结论只能用于证明“readiness 证据源不干净”，不能直接外推真实主线稳定性 |

## 当前 blocker

### Blocker 1
当前已不再是 shadow 代码回归问题，也不再是缺少 source 分离实现；现在的 blocker 是 **需要一个 post-separation 干净观察窗，才能有效重判 readiness 门槛**。

- 2026-04-01 复算：
  - `OpenEmotion/tests/test_response_intent_checker.py`：`47 passed`
  - `OpenEmotion/tests/test_self_report_consistency.py`：`34 passed`
  - `OpenEmotion/tests/test_shadow_mode.py`：`50 passed`
  - `OpenEmotion/tests/test_adversarial_self_report.py`：`77 passed`
- 2026-04-01 fresh shadow 报告：
  - [MVP11_5_shadow_readiness_current_7d.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/self_report/MVP11_5_shadow_readiness_current_7d.md)
    - `4484 checks / 979 violations / 720 numeric leaks`
    - `violation_rate = 21.83%`
    - `numeric_leak_rate = 16.06%`
  - [MVP11_5_shadow_readiness_current_1d.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/artifacts/self_report/MVP11_5_shadow_readiness_current_1d.md)
    - `558 checks / 231 violations / 137 numeric leaks`
    - `violation_rate = 41.4%`
    - `numeric_leak_rate = 24.55%`
- 同一轮分布检查：
  - 7d 窗口 `4127/4484` 条记录 `session_id=''`
  - 其余高频条目主要是 `test_* / parallel_*`
  - 记录在 `2026-03-29` 与 `2026-04-01` 呈单秒级突发
- 2026-04-01 新进展：
  - `SelfReportConsistencyChecker -> ShadowLogger -> shadow_analyzer` 已补上显式 `traffic_source / observation_source`
  - `replay_validator` 已显式写入 `traffic_source=replay`、`observation_source=replay`
  - 定向验证：`test_shadow_mode.py = 56 passed`、`test_response_intent_checker.py -k numeric = 5 passed`
- 这说明当前 blocker 已不再是“宿主 gate 未接 / 无 E4”，也不再是“shadow tests 失败”，更不再是“还没做 source 分离”；真正 blocker 已收敛为 **历史污染日志不会自动回填，当前需要新的干净观察窗**

## 不应误报的事项

- 不能把当前状态报成 `WP1 完成`
- 不能把 `chat_mainline` 的 E4 样本误报成 `WP1 overall ready`
- 不能因为 `memory_claim_gate.py` 已存在就报“memory claim gate 已收口”
- 不能因为 `ResponsePlan` 已接 checker 就报“numeric_leak = 0”

## 进入下一阶段前需要满足的条件

最小条件:
1. 收集带新 source 字段的真实/近真实窗口
2. 基于该干净窗口重跑 readiness 复算，并给出新的 `numeric_leak` 与 SRAP Shadow 结论
3. 明确样本量、误报、漏报门槛是否已满足；若未满足，补观察证据而不是回退代码结论

## 下一步唯一最高优先级动作

先收集带新 source 字段的 post-separation 观察窗，再基于干净窗口重跑 `WP1 readiness`；在这件事完成前，当前仍不应直接推进到 `WP2`。
