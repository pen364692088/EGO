# Memory Model v1

> 文档类型：架构规范  
> 权威源：OpenEmotion  
> 版本：v1.0.0  
> 最后更新：2026-03-15

---

## 1. 概述

OpenEmotion 记忆系统采用三层架构，将原始事件、结构化叙事和长期策略分离存储，实现：

- **时间连续性**：事件不可变，形成连续时间线
- **语义抽象**：叙事聚合事件，形成可理解的故事
- **行为指导**：策略从叙事提炼，指导未来决策

---

## 2. 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Policy Memory                            │
│   长期偏好/约束/原则                                          │
│   - 边界约束                                                  │
│   - 执行原则                                                  │
│   - 学习结果                                                  │
│   ↑ 提炼自叙事                                                │
├─────────────────────────────────────────────────────────────┤
│                   Narrative Memory                           │
│   结构化叙事                                                  │
│   - 项目叙事                                                  │
│   - 关系叙事                                                  │
│   - 学习叙事                                                  │
│   ↑ 聚合自事件                                                │
├─────────────────────────────────────────────────────────────┤
│                     Event Memory                             │
│   原始事件（不可变）                                          │
│   - 会话事件                                                  │
│   - 决策事件                                                  │
│   - 系统事件                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Event Memory - 事件层

### 3.1 职责

| 职责 | 说明 |
|------|------|
| 存储 | append-only，不可变 |
| 查询 | 时间序列、类型过滤 |
| 引用 | 作为叙事层唯一数据源 |

### 3.2 不负责

- 重要性判断
- 聚合/抽象
- 策略生成

### 3.3 数据结构

```python
@dataclass
class Event:
    id: str                    # 唯一标识
    event_type: EventType      # 事件类型
    timestamp: datetime        # 时间戳
    content: str               # 内容
    metadata: dict             # 元数据
    session_id: Optional[str]  # 会话ID
    related_event_ids: list    # 关联事件
```

### 3.4 事件类型

| 类别 | 类型 |
|------|------|
| 会话 | `session_start`, `session_end` |
| 交互 | `user_message`, `agent_response`, `tool_call`, `tool_result` |
| 决策 | `decision_made`, `goal_set`, `goal_completed` |
| 反思 | `reflection_triggered`, `policy_candidate` |
| 系统 | `error`, `milestone`, `boundary_crossing` |

---

## 4. Narrative Memory - 叙事层

### 4.1 职责

| 职责 | 说明 |
|------|------|
| 聚合 | 将相关事件组合成叙事 |
| 维护 | 管理叙事生命周期 |
| 提炼 | 为策略层提供候选素材 |

### 4.2 不负责

- 原始事件存储
- 策略最终决定
- 重要性排序

### 4.3 数据结构

```python
@dataclass
class Narrative:
    id: str                      # 唯一标识
    narrative_type: NarrativeType # 叙事类型
    title: str                   # 标题
    summary: str                 # 摘要
    status: NarrativeStatus      # 状态
    event_ids: list[str]         # 事件引用
    themes: list[str]            # 主题
    key_insights: list[str]      # 洞察
```

### 4.4 叙事类型

| 类别 | 类型 |
|------|------|
| 项目 | `project_start`, `project_progress`, `project_milestone`, `project_completion` |
| 关系 | `relationship_formation`, `relationship_evolution` |
| 学习 | `skill_acquisition`, `knowledge_integration`, `pattern_recognition` |
| 问题 | `problem_encountered`, `problem_solved`, `problem_unsolved` |
| 反思 | `insight`, `behavior_change`, `preference_shift` |

### 4.5 叙事状态

| 状态 | 说明 |
|------|------|
| `active` | 正在发展 |
| `paused` | 暂停/等待 |
| `completed` | 已完结 |
| `superseded` | 被新叙事取代 |

---

## 5. Policy Memory - 策略层

### 5.1 职责

| 职责 | 说明 |
|------|------|
| 存储 | 长期偏好/约束/原则 |
| 生命周期 | 管理提议→采纳→生效→弃用 |
| 应用 | 记录策略被应用的历史 |

### 5.2 不负责

- 策略生成逻辑（由 reflection 模块负责）
- 策略冲突解决
- 策略执行

### 5.3 数据结构

```python
@dataclass
class Policy:
    id: str                      # 唯一标识
    policy_type: PolicyType      # 策略类型
    name: str                    # 名称
    description: str             # 描述
    condition: str               # 触发条件
    action: str                  # 建议行为
    status: PolicyStatus         # 状态
    strength: PolicyStrength     # 强度
    priority: int                # 优先级(0-100)
    source_narrative_ids: list   # 来源叙事
```

### 5.4 策略类型

| 类别 | 类型 |
|------|------|
| 行为约束 | `boundary`, `preference`, `prohibition` |
| 执行原则 | `priority`, `escalation`, `delegation` |
| 学习结果 | `lesson_learned`, `best_practice`, `anti_pattern` |

### 5.5 策略状态

| 状态 | 说明 |
|------|------|
| `proposed` | 提议中 |
| `adopted` | 已采纳 |
| `active` | 生效中 |
| `deprecated` | 已弃用 |
| `rejected` | 已拒绝 |

### 5.6 策略强度

| 强度 | 说明 |
|------|------|
| `soft` | 软约束（可违反） |
| `medium` | 中等约束 |
| `hard` | 硬约束（不可违反） |

---

## 6. 层间关系

```
Event Memory ──聚合──> Narrative Memory ──提炼──> Policy Memory
     ↓                       ↓                        ↓
  不可变                  可变/可修正              可变/可弃用
  原始记录                结构化叙事               行为指导
```

### 6.1 写入规则

1. **Event → Narrative**
   - 叙事通过 `event_ids` 引用事件
   - 事件不可修改
   - 叙事可添加新事件引用

2. **Narrative → Policy**
   - 策略通过 `source_narrative_ids` 引用叙事
   - 策略从叙事提炼，不是从事件
   - 策略可被反思修正

### 6.2 查询规则

1. **自下而上**
   - 策略可追溯到叙事
   - 叙事可追溯到事件
   - 事件不可追溯（是叶子节点）

2. **自上而下**
   - 事件可查找所属叙事
   - 叙事可查找派生策略
   - 策略可查找同源策略

---

## 7. 边界约束

### 7.1 权威源

| 层 | 权威源 |
|------|--------|
| Event Memory | OpenEmotion |
| Narrative Memory | OpenEmotion |
| Policy Memory | OpenEmotion |

### 7.2 EgoCore 限制

EgoCore 可以：
- 读取记忆产物（通过 adapter）
- 缓存摘要/快照
- 在 restore 时注入

EgoCore 禁止：
- 定义记忆字段语义
- 修改记忆内容
- 绕过 OpenEmotion 直接操作记忆

### 7.3 数据流

```
OpenEmotion                    EgoCore
    │                              │
    │  ┌──────────────┐            │
    ├─>│Event Memory  │            │
    │  └──────┬───────┘            │
    │         │                     │
    │  ┌──────▼───────┐            │
    ├─>│Narrative Mem │            │
    │  └──────┬───────┘            │
    │         │                     │
    │  ┌──────▼───────┐   read    ┌┴──────────┐
    └─>│Policy Memory │──────────>│ Adapter   │
       └──────────────┘           └───────────┘
                                         │
                                         │ inject
                                         ▼
                                    ┌──────────┐
                                    │ Runtime  │
                                    └──────────┘
```

---

## 8. 验收标准

### 8.1 功能验收

- [x] 三层职责清晰
- [x] 不再是单层日志式存储
- [x] 同一事件可映射到不同层
- [x] Schema 已定义

### 8.2 边界验收

- [x] 所有记忆模块在 OpenEmotion
- [x] EgoCore 无主体本体代码
- [x] 无双主风险

### 8.3 接口验收

- [x] 可创建事件
- [x] 可创建叙事并引用事件
- [x] 可提议策略并引用叙事
- [x] 可序列化/反序列化

---

## 9. 后续扩展

### 9.1 v1.x（短期）

- Salience：事件重要性判断
- Consolidation：记忆巩固机制
- Forget：遗忘机制

### 9.2 v2.x（中期）

- Relationship Memory：关系演化
- Appraisal Memory：情感评价
- Developmental Memory：发展轨迹

---

## 10. 参考资料

- MVS 任务拆分单
- 边界宪章
- EgoCore × OpenEmotion 边界整改任务单
