# Memory Retrieval Contract v1

## 1. Overview

本文档定义 OpenEmotion 记忆检索层的接口契约。

检索层负责：
- 自动去重 (deduplication)
- 语义聚类 (semantic clustering)
- 向量检索 (vector retrieval)

## 2. 核心原则

1. **用户隔离硬约束**：所有检索操作必须以 user_id 为硬隔离边界
2. **可解释性**：每个检索决策必须留下可审计的 artifact
3. **不静默丢弃**：去重判定必须有明确 reason，不允许静默丢弃
4. **trace_id 审计**：所有操作必须关联 trace_id

## 3. Dedup Contract

### 3.1 输入

```python
@dataclass
class DedupInput:
    event: MemoryEvent           # 待检测事件
    user_id: str                 # 用户ID (必须与 event.user_id 一致)
    trace_id: str                # 审计追踪ID
```

### 3.2 输出

```python
@dataclass
class DedupResult:
    event_id: str                # 事件ID
    dedup_status: str            # 'unique' | 'exact_duplicate' | 'near_duplicate'
    dedup_reason: str            # 判定原因
    matched_event_id: Optional[str]  # 匹配的已有事件ID (重复时)
    similarity_score: float      # 相似度分数 (0.0-1.0)
    trace_id: str                # 审计追踪ID
    timestamp: str               # 判定时间
```

### 3.3 Dedup Status 定义

| Status | 含义 | 行为 |
|--------|------|------|
| `unique` | 新唯一事件 | 正常写入记忆 |
| `exact_duplicate` | 完全重复 | 抑制写入，记录 artifact |
| `near_duplicate` | 近似重复 | 根据策略决定是否更新已有叙事 |

### 3.4 判定规则

**Exact Duplicate 条件**：
- payload 所有字段完全相同
- 且 event_type 相同

**Near Duplicate 条件**：
- 文本相似度 >= 0.85
- 或核心字段重叠 >= 80%
- 且 event_type 相同

### 3.5 配置

```python
DEDUP_CONFIG = {
    "exact_threshold": 1.0,      # 完全匹配阈值
    "near_threshold": 0.85,      # 近似匹配阈值
    "lookback_events": 50,       # 检查最近 N 条事件
    "text_fields": ["content", "summary", "description"],  # 参与文本相似度计算的字段
}
```

## 4. Clustering Contract

### 4.1 输入

```python
@dataclass
class ClusteringInput:
    events: List[MemoryEvent]    # 待聚类事件列表
    user_id: str                 # 用户ID (必须与所有 event.user_id 一致)
    trace_id: str                # 审计追踪ID
```

### 4.2 输出

```python
@dataclass
class Cluster:
    cluster_id: str              # 聚类ID
    user_id: str                 # 用户ID
    event_ids: List[str]         # 聚类内事件ID列表
    theme: str                   # 聚类主题
    summary: str                 # 聚类摘要
    confidence: float            # 置信度 (0.0-1.0)
    created_at: str              # 创建时间
    updated_at: str              # 更新时间

@dataclass
class ClusteringResult:
    clusters: List[Cluster]      # 聚类结果
    user_id: str                 # 用户ID
    trace_id: str                # 审计追踪ID
    timestamp: str               # 聚类时间
```

### 4.3 Cluster 输出字段要求

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| cluster_id | str | ✅ | 唯一标识 |
| user_id | str | ✅ | 所属用户 |
| event_ids | List[str] | ✅ | 成员事件ID |
| theme | str | ✅ | 主题关键词 |
| summary | str | ✅ | 摘要描述 |
| confidence | float | ✅ | 聚类置信度 |

### 4.4 Cluster -> Narrative 映射

- 每个 cluster 可映射到 0 或 1 个 narrative 候选
- 映射规则：cluster.theme 与 narrative.theme 匹配
- 映射置信度 = cluster.confidence × narrative.confidence

## 5. Vector Retrieval Contract

### 5.1 输入

```python
@dataclass
class RetrievalQuery:
    query_text: str              # 查询文本
    user_id: str                 # 用户ID (硬隔离)
    top_k: int                   # 返回数量
    trace_id: str                # 审计追踪ID
    filters: Optional[Dict]      # 可选过滤条件
```

### 5.2 输出

```python
@dataclass
class RetrievalHit:
    id: str                      # 命中的 narrative/policy ID
    type: str                    # 'narrative' | 'policy'
    similarity_score: float      # 相似度分数 (0.0-1.0)
    matched_text: str            # 匹配的文本内容
    metadata: Dict               # 元数据

@dataclass
class RetrievalResult:
    query: str                   # 原始查询
    user_id: str                 # 用户ID
    hits: List[RetrievalHit]     # 命中结果 (按 similarity_score 降序)
    trace_id: str                # 审计追踪ID
    timestamp: str               # 检索时间
```

### 5.3 top-k 结构

```python
top_k_result = {
    "hit_1": {
        "id": "narrative_abc123",
        "type": "narrative",
        "similarity_score": 0.92,
        "matched_text": "...",
    },
    "hit_2": { ... },
    # ... up to top_k
}
```

### 5.4 User ID 过滤规则

**硬约束**：
- 所有检索查询必须包含 user_id 参数
- 不允许省略 user_id
- 不允许使用通配符 user_id
- 返回结果只包含该 user_id 的数据

**检查点**：
```python
assert query.user_id is not None
assert query.user_id != "*"
assert all(hit.user_id == query.user_id for hit in result.hits)
```

## 6. 端到端流程

```
event 输入
    ↓
[Dedup Check] → unique → 写入存储
    ↓                 → duplicate → 记录 artifact，抑制写入
[SQLite Store]
    ↓
[Clustering] → 更新/创建 cluster
    ↓
[Vector Index] → 建立向量索引
    ↓
[Retrieval] → 命中 narrative/policy
    ↓
downstream effect
```

## 7. 禁止事项

1. **禁止跨用户检索**：任何情况下不允许跨 user_id 召回
2. **禁止静默丢弃**：去重必须有 artifact
3. **禁止黑盒聚类**：cluster 必须有可解释的 theme/summary
4. **禁止绕过 dedup**：所有事件必须经过 dedup 检查

## 8. 版本

- v1.0.0: 初始契约定义 (2026-03-16)
