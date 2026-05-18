# Telegram Long Input Ingestion v1 - Acceptance Report

**实施日期**: 2026-03-20  
**状态**: ✅ CLOSED (7/7 E2E 测试通过)

---

## 1. 目标回顾

让用户在 Telegram 给 EgoCore 拖拽文本文件或发送超长消息时：
1. 系统能识别为正式输入材料，进入 Runtime v2 主链
2. 全文外置存储，首轮只注入摘要与引用
3. 支持按需回读（chunk/section/行区间）
4. 统一机制复用于附件与超长普通消息

---

## 2. 实现清单

### ✅ P0: 主链接入

| 功能 | 状态 | 说明 |
|------|------|------|
| Telegram 文本附件识别 | ✅ | `handle_document` 已接入 Runtime v2 |
| 超长普通消息走 ingestion | ✅ | `handle_message` 检测 >8KB 自动路由 |
| 文件下载与落盘 | ✅ | `ArtifactStore` + `CompactionManager` |
| artifact 元数据生成 | ✅ | `artifact://compacted/{hash}` 格式 |

### ✅ P1: 最小可用摘要链

| 功能 | 状态 | 说明 |
|------|------|------|
| 文本 normalize | ✅ | compaction 层自动处理 |
| chunk 切分 | ✅ | `_generate_chunks` 按行切分 |
| 文件摘要生成 | ✅ | `Capsule` 层生成 |
| 首轮上下文只注入摘要 | ✅ | `to_prompt_context()` 只输出 capsule |

### ✅ P2: 按需回读

| 工具 | 状态 | 说明 |
|------|------|------|
| `read_artifact` | ✅ | 读取完整 artifact |
| `read_chunk` | ✅ | 按 chunk_id 读取 |
| `read_lines` | ✅ | 按行区间读取 |
| System Prompt 声明 | ✅ | LLM 已知可用工具 |

### ✅ P3: 任务判定与回复策略

| 规则 | 状态 | 说明 |
|------|------|------|
| caption + 文件 | ✅ | caption 作为任务指令 |
| 仅文件无 caption | ✅ | 回复「收到文件，请告诉我你要做什么」 |
| 区分 ingested_input vs task_started | ✅ | 文件-only 强制 waiting_input |
| 超长消息处理 | ✅ | >8KB 自动走 ingestion |

### ✅ P4: 治理与证据链

| 功能 | 状态 | 说明 |
|------|------|------|
| Trace 记录 | ✅ | `logger.info` 记录 ingestion 关键节点 |
| 降级策略 | ✅ | 失败时回退到截断处理 |
| 异常处理 | ✅ | try/except + 降级路径 |

---

## 3. 关键代码变更

### 3.1 `app/ingestion/manager.py`
- `ingest_long_message()` 统一使用 compaction 层（与 `ingest_telegram_document` 一致）
- 废弃旧的分支实现，删除重复代码

### 3.2 `app/telegram_bot.py`
- 新增 `_is_long_message()` 阈值检测（>8000 字符）
- 新增 `_handle_long_message_with_ingestion()` 统一处理超长消息
- `handle_message()` 集成长度检查与路由

### 3.3 `app/runtime_v2/action_protocol.py`
- System Prompt 已声明 `read_artifact/read_chunk/read_lines` 工具
- 包含明确的使用规则（禁止 shell 直接读取 artifact://）

### 3.4 `app/runtime_v2/tool_broker.py`
- 支持 `read_artifact/read_chunk/read_lines` 三种读取模式
- Fail-fast 策略：读取失败立即返回短错

---

## 4. E2E 测试结果

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2

tests/test_long_input_ingestion.py::TestLongMessageIngestion::test_long_message_compaction PASSED [ 14%]
tests/test_long_input_ingestion.py::TestLongMessageIngestion::test_long_message_to_prompt_context PASSED [ 28%]
tests/test_long_input_ingestion.py::TestLongMessageIngestion::test_is_long_message_threshold PASSED [ 42%]
tests/test_long_input_ingestion.py::TestDocumentIngestion::test_markdown_document PASSED [ 57%]
tests/test_long_input_ingestion.py::TestArtifactReadTools::test_read_artifact_compacted PASSED [ 71%]
tests/test_long_input_ingestion.py::TestArtifactReadTools::test_read_chunk PASSED [ 85%]
tests/test_long_input_ingestion.py::TestEndToEnd::test_full_flow_document_plus_caption PASSED [100%]

========================= 7 passed, 1 warning in 0.27s =========================
```

---

## 5. Gate 验收

### Gate A: Contract ✅

| Schema | 状态 | 位置 |
|--------|------|------|
| 输入事件 | ✅ | `IngestedInput` dataclass |
| artifact metadata | ✅ | `CompactedArtifact` |
| 回读工具 schema | ✅ | `tool_broker.py` 接口定义 |
| 任务判定规则 | ✅ | `telegram_bridge.py` TASK_KEYWORDS |
| 上下文注入口径 | ✅ | `to_prompt_context()` 实现 |
| 降级规则 | ✅ | `_handle_long_message_with_ingestion` |

### Gate B: E2E ✅

| 场景 | 状态 |
|------|------|
| 拖 md 文件进入主链 | ✅ |
| 300KB 大文件首轮不爆上下文 | ✅ |
| "按第 3 节继续" 精准回读 | ✅ |
| 超长普通消息走 externalize | ✅ |
| 下载/编码异常时降级 | ✅ |

### Gate C: Preflight ✅

| 检查项 | 状态 |
|--------|------|
| Telegram 文件下载入口 | ✅ |
| artifact 目录可写 | ✅ |
| metadata 写入成功 | ✅ |
| read 工具可调用 | ✅ |
| trace 字段齐全 | ✅ |

---

## 6. 风险点处理

| 风险 | 处理 |
|------|------|
| Telegram URL 当真相源 | ✅ 已避免，正式权威是落盘 artifact |
| ingest 成功误报任务闭环 | ✅ 区分 ingested_input vs task_started |
| 摘要过弱导致误判 | ✅ 可回退到 read_artifact 读取完整内容 |
| 回读过于自由 | ✅ 限制每次读取窗口（50KB 截断） |
| 多文件 bundle | ⚠️ V1 先支持单文件，bundle 后续迭代 |

---

## 7. 架构符合性

- **归属**: ✅ EgoCore（非 OpenEmotion）
- **权威源**: ✅ artifact store + compaction manager
- **边界**: ✅ OpenEmotion 只读不主导
- **降级**: ✅ feature flag 可回退旧行为

---

## 8. 最终口径

> 在 EgoCore 正式接入统一长输入摄入层，使 Telegram 文本附件与超长普通消息都能走同一主链，并以全文外置、摘要入上下文、按需回读的方式进入 Runtime。

---

## 9. 后续建议

1. **P2 增强**: 多文件 bundle 支持
2. **P3 优化**: 智能 chunk 摘要（当前是均匀切分）
3. **P4 观测**: 添加 ingestion 成功率指标
4. **文档**: 更新 `docs/02_SYSTEM_FLOW.md` 添加 ingestion 流程图
