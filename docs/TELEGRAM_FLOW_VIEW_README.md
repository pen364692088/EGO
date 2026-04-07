# Telegram Flow View

`/flow` 与 `/samples/<sample_id>/flow` 是现有 `dashboard_v1` 上的只读解释层页面。

目标只有两个：

- 把单轮样本重组为 `Input -> Host Ingress -> Subject Understanding -> Host Arbitration -> Output`
- 让人一眼看出这条链有没有通、哪里降级、主体到底基于什么上下文和倾向在工作

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
4. 宿主最后如何裁决和输出
5. 这条链是否贯通、是否 degraded、是否仍是 host-only

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
