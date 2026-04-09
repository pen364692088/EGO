# Telegram Flow View

`/flow` 与 `/samples/<sample_id>/flow` 是现有 `dashboard_v1` 上的只读解释层页面。

目标只有两个：

- 把单轮样本重组为 `Input -> Host Ingress -> Subject Understanding -> Canonical Fields -> Reply Evolution -> Host Arbitration -> Output`
- 让人一眼看出这条链有没有通、哪里降级、主体到底基于什么上下文和倾向在工作

## 当前权威状态（2026-04-09）

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 这是 repo/integration scope closeout，不是 real-channel 新效果声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`

## 当前正式口径

- 本文件是只读解释层说明，不升格为 authority source
- `/flow` 与 `/samples/<sample_id>/flow` 只解释当前样本与 current artifacts，不代表额外主权威
- 解释层看到的 current state 仍要回到原始 artifacts 和 closeout evidence 交叉确认

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`

## 当前权威入口

- [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
- [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)
- [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
- [ACCEPTANCE_CHAINS.md](ACCEPTANCE_CHAINS.md)

## 历史与详细证据入口

- 下方页面解释规则与字段说明保留为详细说明，不是新的 authority source
- 具体 current state / closeout proof 仍以对应文档与原始 artifacts 为准

## 权威边界

- 这不是新的 authority source
- 所有判断都来自只读派生：
  - `ledger.json`
  - `openemotion_result.json`
  - `openemotion_trace.json`
  - `response_plan.json`
  - `outbox_record.json`
  - `timeline.json`
- 若页面摘要与原始 artifact 冲突，以 artifact 为准

## 受控摘要原则

- 默认只显示受控摘要，不展示原始长 prompt
- 页面里的“主体理解”是解释层，不替代原始 `trace_payload`
- 每段都可展开到底层字段，查看：
  - 来源 artifact
  - 原始字段路径
  - 原始字段值

## 用法

启动 dashboard：

```bash
cd EgoCore
PYTHONPATH=. python3 -m app.main --dashboard --host 127.0.0.1 --port 8787
```

页面：

- `/flow`
  - 最新样本的流程解释页
- `/samples/<sample_id>/flow`
  - 指定样本的流程解释页

## 页面回答的问题

每轮样本都固定回答：

1. 输入是什么，宿主怎么理解
2. 宿主是否把它送进了主体
3. 主体看到了哪些上下文、当前主要倾向是什么
4. 主体关键字段到底是什么：`loaded_axes / identity_delta / self_model_delta / drives_delta / policy_hint / response_tendency`
5. 宿主最后如何裁决和输出
6. 这轮是不是 recent-result continuation，`parser_source / request_mode / pending continuation / correction_context` 是什么
7. 这条链是否贯通、是否 degraded、是否仍是 host-only

## Reply Evolution

`Reply Evolution` 第一版是 evidence-only 解释层。

- 它展示的是：
  - 主体修正信号
  - 宿主裁决
  - 最终输出
- 它不是：
  - 原始 LLM 草稿 vs 修正后文本的直接 diff

当前只覆盖 `chat_mainline`。

如果样本只证明：
- `message_sent = true`
- `text_length / reply_length` 存在
- 但最终文本没有被 artifacts 持久化

页面会明确显示：
- `final_text_capture_status = missing_but_delivered`
- `reply_length`

这表示链路已经送出消息，但当前证据包没有保存最终文本预览，不是页面渲染故障。

以下路径会明确显示 `not_available`：

- `task_mainline`
- `host_degraded_fallback`
- `host_only`
- `command/status/evidence` 等非 chat 主线

如果后续需要真正显示 `base_draft -> final_output`，必须先在主链新增 repo-tracked draft capture，再升级这个视图。

## Canonical Fields

`Canonical Fields` 是 `/flow` 的固定审计层，用来把最关键的主体与宿主字段直接摆到主视图里，而不是埋在 engineering fields。

固定字段：

- `loaded_axes`
- `identity_delta`
- `self_model_delta`
- `drives_delta`
- `policy_hint`
- `response_tendency`
- `host_arbitration_result`
- `final_delivered_text`

`final_delivered_text` 当前使用 bounded persistence：

- 优先显示 `response_plan.reply_text`
- 否则显示 `response_plan.metadata.final_text_preview`
- 再否则显示 `outbox_record.final_text_preview`
- 若仍不存在，才显示 `missing_but_delivered`

这表示：

- “链路贯通”
- 和“最终文本是否被 bounded 持久化”

是两个不同检查项。

## Host Ingress 审计字段

当前 `/flow` 的 `Host Ingress` 主视图会直接显示：

- `runtime_path`
- `parser_source`
- `request_mode`
- `recent_result_binding`
- `pending_result_continuation`
- `correction_context`

这一层是为了回答：

- 这轮是 semantic parser 还是 heuristic fallback 判的
- 这轮是普通 chat、`analyze`、`write` 还是 status continuation
- 宿主为什么把它当成 recent-result continuation，而不是普通聊天
