# Proto-Self Kernel v1 接口与伪代码草案

> 状态补充：V1 interface draft / historical implementation bridge
> 与 V2 关系：它不是 `Proto-Self V2` 的 canonical source
> V2 正式规格：`docs/PROTO_SELF_KERNEL_V2_SPEC.md`
> V2 迁移映射：`docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md`

> 项目：EgoCore + OpenEmotion
> 类型：工程草案 / 接口与伪代码
> 状态：设计完成，未启用
> 目标：给出一个 **可在 OpenEmotion 内落地**、**可由 EgoCore 宿主承接**、**不破坏双核边界** 的最小主体内核 v1

---

## 0. 一句话定义

**Proto-Self Kernel v1 = 一个统一递归更新器 + 4 类核心状态 + 结构化输入输出契约 + 明确后果回流。**

它不直接说话，不直接执行工具，不直接拥有现实裁决权。
它只负责回答：

* 我现在是谁
* 我刚刚经历了什么
* 这些经历如何改变我
* 当前内部张力如何影响下一步倾向
* 哪些 recurring structures 值得固化成 cycle

这与现有边界宪章一致：
EgoCore 负责与世界交互、运行、执行、治理；OpenEmotion 负责 identity、self-model、memory、appraisal、reflection 的本体解释权。

---

## 1. 当前层级与验收口径

### 当前层级

MVS / proto-self kernel 层，不是开放发展式自我层。当前主线明确要求先做最小可持续主体，再进入 developmental self。

### 当前确定项

* 双核架构已经收口：EgoCore 外壳，OpenEmotion 内核。
* OpenEmotion 的 North Star 已经要求：self-model invariants、emotion as functional bias、全链路可审计/可回放。
* Cycle 已被定义为一等公民，且必须可重入、可固化、可回放。
* 开发核一开始不能直接拿最终说话权与执行权，只能在壳里长。

### 还没完成什么

* 还没有正式 schema
* 还没有 runtime adapter
* 还没有 trace/replay 接线
* 还没有真实 E2E 证据

所以这份文档只能称为：**已设计，待实现与验证**。

---

## 2. 目录建议

Proto-Self Kernel v1 建议正式落在 **OpenEmotion**，EgoCore 只保留 adapter / mirror / restore / runtime judgment。这个分层与边界宪章一致。

```text
openemotion/
  proto_self/
    __init__.py
    schemas.py           # 输入输出 schema / dataclass
    state.py             # ProtoSelfState / CycleSignature
    kernel.py            # process_event 主循环
    appraisal.py         # drive_field 更新
    self_model.py        # self_model 更新
    cycles.py            # cycle consolidation
    reflection.py        # reflection note
    reducers.py          # apply_updates / state writeback
    trace_types.py       # 可写入 run.jsonl 的 trace 结构
    tests/
      test_kernel_identity.py
      test_kernel_drive_field.py
      test_kernel_cycles.py
      test_kernel_reflection.py
      test_kernel_boundaries.py
```

EgoCore 侧只新增最薄的一层：

```text
egocore/
  app/
    openemotion_adapter/
      proto_self_adapter.py
      proto_self_restore.py
      proto_self_trace_bridge.py
```

---

## 3. 最小核心状态

v1 只保留 4+1 个状态对象。

### 3.1 `identity_invariants`

负责"还是不是同一个我"。

```python
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class IdentityInvariants:
    core_roles: List[str] = field(default_factory=list)
    core_commitments: List[str] = field(default_factory=list)
    core_boundaries: List[str] = field(default_factory=list)
    stable_preferences: Dict[str, float] = field(default_factory=dict)
    identity_confidence: float = 0.5
```

### 3.2 `self_model`

负责"我怎样看自己"。

```python
@dataclass
class SelfModel:
    capabilities: Dict[str, float] = field(default_factory=dict)
    limitations: Dict[str, float] = field(default_factory=dict)
    current_focus: str | None = None
    current_mode: str = "baseline"
    self_confidence_by_domain: Dict[str, float] = field(default_factory=dict)
```

### 3.3 `drive_field`

负责"什么内部张力在推动我"。

```python
@dataclass
class DriveField:
    coherence_pressure: float = 0.0
    curiosity: float = 0.0
    caution: float = 0.0
    completion_pressure: float = 0.0
    social_tension: float = 0.0
```

### 3.4 `cycle_store`

负责"哪些结构反复出现并值得重入"。

```python
@dataclass
class CycleSignature:
    cycle_id: str
    psi_bucket: str
    phi_signature: str
    strength: float
    hits: int
    last_seen_ts: str
    promoted: bool = False

@dataclass
class CycleStore:
    signatures: Dict[str, CycleSignature] = field(default_factory=dict)
```

### 3.5 `episodic_trace`

负责"最近发生了什么以及后果如何"。

```python
from collections import deque
from typing import Any

@dataclass
class EpisodicRecord:
    event_id: str
    perceived_summary: Dict[str, Any]
    action_hint: Dict[str, Any]
    external_result: Dict[str, Any] | None
    appraisal_snapshot: Dict[str, float]

@dataclass
class ProtoSelfState:
    identity: IdentityInvariants
    self_model: SelfModel
    drives: DriveField
    cycle_store: CycleStore
    episodic_trace: deque
    revision_counter: int = 0
```

---

## 4. 输入输出契约

这里必须严格服从现有边界文档：
EgoCore → OpenEmotion 是**结构化事件**；OpenEmotion → EgoCore 是**结构化结果**；禁止靠 prompt 文本临时约定字段。

### 4.1 EgoCore → OpenEmotion 输入

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class KernelEvent:
    schema_version: str
    event_id: str
    timestamp: str
    actor: str
    source: str
    event_type: str

    user_intent: Optional[str] = None
    raw_text: Optional[str] = None

    conversation_context: Dict[str, Any] = field(default_factory=dict)
    task_context: Dict[str, Any] = field(default_factory=dict)
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    safety_context: Dict[str, Any] = field(default_factory=dict)
    external_result: Optional[Dict[str, Any]] = None
```

#### 字段设计说明

* `schema_version`：避免接口漂移
* `runtime_summary`：让 OpenEmotion 感知当前外部运行态，但不拿走运行时真相源
* `external_result`：让"后果回流"成为一等输入，而不是可有可无的日志尾巴

---

### 4.2 OpenEmotion → EgoCore 输出

```python
@dataclass
class ReflectionNote:
    trigger: str
    diagnosis: str
    proposed_adjustment: Dict[str, Any]
    promote_to_memory: bool = False

@dataclass
class ResponseTendency:
    preferred_mode: str
    preferred_tone: str
    certainty_bound: str
    suggested_next_step: str
    ask_needed: bool = False

@dataclass
class KernelOutput:
    schema_version: str
    event_id: str

    identity_state_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    relationship_update: Dict[str, Any] = field(default_factory=dict)
    appraisal_state_delta: Dict[str, Any] = field(default_factory=dict)

    reflection_note: ReflectionNote | None = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: ResponseTendency | None = None
    confidence_meta: Dict[str, Any] = field(default_factory=dict)

    trace_payload: Dict[str, Any] = field(default_factory=dict)
```

#### 输出约束

* `policy_hint` / `response_tendency` 只表达建议与倾向
* **不能包含直接工具执行命令**
* **不能直接替 EgoCore 做现实裁决**
* 自由文本只能放在 `diagnosis` 或 explanation 字段，程序消费依然依赖结构字段

这与边界宪章里"OpenEmotion 允许提供 response_tendency / policy_hint / reflection candidate，但不能越过 EgoCore 直接执行现实动作"完全一致。

---

## 5. 主循环

Proto-Self Kernel v1 的主循环只做一件事：
**把事件、当前自我状态、历史轨迹、外部后果重新折叠成"下一状态 + 下一步倾向"。**

```python
def process_event(state: ProtoSelfState, event: KernelEvent) -> KernelOutput:
    perceived = perceive(event, state)
    appraisal_delta = update_drive_field(state, perceived)
    self_model_delta = update_self_model(state, perceived, appraisal_delta)
    cycle_delta = consolidate_cycles(state, perceived, appraisal_delta, self_model_delta)
    reflection_note = maybe_reflect(state, event, perceived, appraisal_delta, self_model_delta)
    identity_delta = update_identity_invariants(state, perceived, reflection_note)
    memory_update = update_memory(state, perceived, cycle_delta, reflection_note)
    policy_hint = derive_policy_hint(state, appraisal_delta, self_model_delta, identity_delta)
    response_tendency = derive_response_tendency(state, policy_hint)
    next_state = apply_updates(
        state=state,
        event=event,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        identity_delta=identity_delta,
        memory_update=memory_update,
        reflection_note=reflection_note,
    )
    trace_payload = build_trace_payload(
        event=event,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        reflection_note=reflection_note,
        policy_hint=policy_hint,
    )
    return KernelOutput(
        schema_version="proto_self.v1",
        event_id=event.event_id,
        identity_state_delta=identity_delta,
        self_model_delta=self_model_delta,
        memory_update=memory_update,
        appraisal_state_delta=appraisal_delta,
        reflection_note=reflection_note,
        policy_hint=policy_hint,
        response_tendency=response_tendency,
        confidence_meta=compute_confidence_meta(next_state),
        trace_payload=trace_payload,
    )
```

---

## 6. 各函数职责

### 6.1 `perceive()`

把事件压成最小可更新语义，不做大而全 NLU。

```python
def perceive(event: KernelEvent, state: ProtoSelfState) -> dict:
    return {
        "intent": event.user_intent,
        "novelty": score_novelty(event, state),
        "identity_conflict": score_identity_conflict(event, state),
        "unfinished_commitment": score_unfinished_commitment(event, state),
        "risk_signal": score_risk(event.safety_context),
        "relational_mismatch": score_relation_mismatch(event, state),
        "external_outcome_type": classify_external_result(event.external_result),
    }
```

### 6.2 `update_drive_field()`

把 appraisal 当成功能性偏置，而不是情绪文案。OpenEmotion 当前架构明确要求 emotion as functional bias。

```python
def update_drive_field(state: ProtoSelfState, perceived: dict) -> dict:
    return {
        "coherence_pressure": clamp(
            state.drives.coherence_pressure + perceived["identity_conflict"] * 0.4
        ),
        "curiosity": clamp(
            state.drives.curiosity + perceived["novelty"] * 0.3 - perceived["risk_signal"] * 0.1
        ),
        "caution": clamp(
            state.drives.caution + perceived["risk_signal"] * 0.5
        ),
        "completion_pressure": clamp(
            state.drives.completion_pressure + perceived["unfinished_commitment"] * 0.4
        ),
        "social_tension": clamp(
            state.drives.social_tension + perceived["relational_mismatch"] * 0.4
        ),
    }
```

### 6.3 `update_self_model()`

只做最小可测更新，不做"人格大杂烩"。

```python
def update_self_model(state: ProtoSelfState, perceived: dict, appraisal_delta: dict) -> dict:
    delta = {"capabilities": {}, "limitations": {}, "current_focus": None, "current_mode": None}

    if perceived["risk_signal"] > 0.7:
        delta["current_mode"] = "cautious"

    if appraisal_delta["completion_pressure"] > 0.6:
        delta["current_focus"] = "closure"

    return delta
```

### 6.4 `consolidate_cycles()`

这里要对齐现有 Cycle 治理：cycle 必须是稳定低熵、可重入、可写 trace、可 replay 的结构。

```python
def consolidate_cycles(state: ProtoSelfState, perceived: dict, appraisal_delta: dict, self_model_delta: dict) -> dict:
    psi_bucket = build_psi_bucket(perceived)
    phi_signature = build_phi_signature(appraisal_delta, self_model_delta)

    cycle_id = stable_hash(f"{psi_bucket}|{phi_signature}")
    existing = state.cycle_store.signatures.get(cycle_id)

    if existing:
        return {
            "cycle_id": cycle_id,
            "op": "strengthen",
            "psi_bucket": psi_bucket,
            "phi_signature": phi_signature,
            "strength_delta": 0.1,
        }

    return {
        "cycle_id": cycle_id,
        "op": "candidate",
        "psi_bucket": psi_bucket,
        "phi_signature": phi_signature,
        "strength_delta": 0.05,
    }
```

### 6.5 `maybe_reflect()`

反思只在必要时触发，不能把 reflection 做成第二个大脑。

```python
def maybe_reflect(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: dict,
    appraisal_delta: dict,
    self_model_delta: dict,
) -> ReflectionNote | None:
    if perceived["external_outcome_type"] == "failure":
        return ReflectionNote(
            trigger="external_failure",
            diagnosis="recent action did not achieve expected outcome",
            proposed_adjustment={"current_mode": "repair", "raise_caution": True},
            promote_to_memory=True,
        )

    if perceived["identity_conflict"] > 0.7:
        return ReflectionNote(
            trigger="identity_conflict",
            diagnosis="event conflicts with core commitments or boundaries",
            proposed_adjustment={"strengthen_boundary_review": True},
            promote_to_memory=False,
        )

    return None
```

### 6.6 `update_identity_invariants()`

只有高价值证据才能动 identity，不允许"一次事件改人格"。

```python
def update_identity_invariants(
    state: ProtoSelfState,
    perceived: dict,
    reflection_note: ReflectionNote | None,
) -> dict:
    delta = {
        "core_roles_add": [],
        "core_commitments_add": [],
        "core_boundaries_add": [],
        "stable_preferences_patch": {},
        "identity_confidence_delta": 0.0,
    }

    if reflection_note and reflection_note.trigger == "identity_conflict":
        delta["identity_confidence_delta"] = -0.05

    return delta
```

### 6.7 `update_memory()`

v1 不做大而全记忆系统，只做：

* episodic_trace 写入
* cycle 相关 promotion hint
* reflection note promotion hint

```python
def update_memory(
    state: ProtoSelfState,
    perceived: dict,
    cycle_delta: dict,
    reflection_note: ReflectionNote | None,
) -> dict:
    return {
        "append_episode": True,
        "cycle_promotion_candidate": cycle_delta["cycle_id"],
        "promote_reflection": bool(reflection_note and reflection_note.promote_to_memory),
    }
```

### 6.8 `derive_policy_hint()` / `derive_response_tendency()`

这一步只产出倾向，不抢 EgoCore 的 response plan / intent contract / outward contract 主权。现有路线已经明确表达主权要由 EgoCore 程序端控制。

```python
def derive_policy_hint(
    state: ProtoSelfState,
    appraisal_delta: dict,
    self_model_delta: dict,
    identity_delta: dict,
) -> dict:
    return {
        "risk_bias": "high" if appraisal_delta["caution"] > 0.7 else "normal",
        "closure_bias": appraisal_delta["completion_pressure"] > 0.6,
        "ask_preferred": appraisal_delta["caution"] > 0.8,
        "should_avoid_commitment_upgrade": True,
    }

def derive_response_tendency(state: ProtoSelfState, policy_hint: dict) -> ResponseTendency:
    return ResponseTendency(
        preferred_mode="ask" if policy_hint["ask_preferred"] else "respond",
        preferred_tone="calm",
        certainty_bound="bounded",
        suggested_next_step="clarify_or_repair" if policy_hint["closure_bias"] else "continue",
        ask_needed=policy_hint["ask_preferred"],
    )
```

---

## 7. 状态写回

```python
def apply_updates(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: dict,
    appraisal_delta: dict,
    self_model_delta: dict,
    cycle_delta: dict,
    identity_delta: dict,
    memory_update: dict,
    reflection_note: ReflectionNote | None,
) -> ProtoSelfState:
    # 1. 写 appraisal
    state.drives.coherence_pressure = appraisal_delta["coherence_pressure"]
    state.drives.curiosity = appraisal_delta["curiosity"]
    state.drives.caution = appraisal_delta["caution"]
    state.drives.completion_pressure = appraisal_delta["completion_pressure"]
    state.drives.social_tension = appraisal_delta["social_tension"]

    # 2. 写 self_model
    if self_model_delta.get("current_focus") is not None:
        state.self_model.current_focus = self_model_delta["current_focus"]
    if self_model_delta.get("current_mode") is not None:
        state.self_model.current_mode = self_model_delta["current_mode"]

    # 3. 写 cycle
    apply_cycle_delta(state.cycle_store, cycle_delta, event.timestamp)

    # 4. 写 episodic_trace
    state.episodic_trace.append(
        EpisodicRecord(
            event_id=event.event_id,
            perceived_summary=perceived,
            action_hint={},
            external_result=event.external_result,
            appraisal_snapshot=appraisal_delta,
        )
    )

    # 5. revision counter
    if reflection_note:
        state.revision_counter += 1

    return state
```

---

## 8. EgoCore 宿主侧接线

这部分必须很薄，因为边界宪章已经禁止 EgoCore 偷做 self-model / memory / appraisal / reflection 本体。

```python
class ProtoSelfAdapter:
    def __init__(self, kernel, cache, trace_bridge):
        self.kernel = kernel
        self.cache = cache
        self.trace_bridge = trace_bridge

    def handle_event(self, egocore_event: dict) -> dict:
        kernel_event = normalize_to_kernel_event(egocore_event)
        state = self.cache.load_latest_state()
        result = self.kernel.process_event(state, kernel_event)

        self.cache.save_mirror(result)
        self.trace_bridge.write(result.trace_payload)

        return {
            "policy_hint": result.policy_hint,
            "response_tendency": result.response_tendency,
            "identity_state_delta": result.identity_state_delta,
            "self_model_delta": result.self_model_delta,
            "appraisal_state_delta": result.appraisal_state_delta,
            "reflection_note": result.reflection_note,
        }
```

### 宿主侧允许做的事

* 事件标准化
* restore 注入
* latest state mirror
* trace 写桥
* 与 response plan / intent contract / runtime safety 结合后做最终裁决

### 宿主侧禁止做的事

* 自己改写 identity invariants
* 自己定义 appraisal state 语义
* 自己做长期 self-model 更新本体
* 自己把 reflection 结论当正式真相源

---

## 9. Trace / Replay 接口

因为现有主线已经把 deterministic、trace-driven replay、artifact discipline 立为硬要求，所以 Proto-Self Kernel 不能做"黑箱更新"。

建议每轮写这几个字段进 trace：

```python
trace_payload = {
    "kernel_version": "proto_self.v1",
    "event_id": event.event_id,
    "perceived": perceived,
    "appraisal_delta": appraisal_delta,
    "self_model_delta": self_model_delta,
    "cycle_delta": cycle_delta,
    "identity_delta": identity_delta,
    "reflection_trigger": reflection_note.trigger if reflection_note else None,
    "policy_hint": policy_hint,
}
```

### 回放要求

* replay 时优先读取 trace 中已记录的 `cycle_delta` / `policy_hint`
* 不允许用"当前 cycle_store 现状"去重算旧轮结果
* 这样才不会破坏 anti-drift 与 trace-driven replay

---

## 10. 最小测试骨架

### 10.1 身份连续性

```python
def test_identity_invariants_do_not_jump_without_evidence():
    ...
```

目标：无高价值冲突证据时，identity 不应乱跳。

### 10.2 drive 有行为效应

```python
def test_high_caution_changes_response_tendency():
    ...
```

目标：高 caution 必须改变 response_tendency，而不是只体现在文本里。

### 10.3 cycle 可重入

```python
def test_repeated_pattern_strengthens_cycle():
    ...
```

目标：反复相似事件应强化同一 cycle_id。

### 10.4 反思可写回

```python
def test_failure_generates_reflection_note_and_revision():
    ...
```

目标：失败会触发 reflection，并改变 revision_counter / 下一轮 mode。

### 10.5 边界无越权

```python
def test_kernel_never_returns_direct_tool_execution():
    ...
```

目标：输出只允许 suggestion / tendency / policy_hint，不允许直接执行命令。

### 10.6 replay 兼容

```python
def test_trace_payload_is_sufficient_for_replay():
    ...
```

目标：trace 中有足够字段支撑旧轮重放，不依赖当前 store 重算。

---

## 11. 实现顺序

### 第一步

先实现：

* `schemas.py`
* `state.py`
* `kernel.py`
* `tests/test_kernel_identity.py`

### 第二步

补：

* `appraisal.py`
* `self_model.py`
* `cycles.py`

### 第三步

接入：

* EgoCore `proto_self_adapter.py`
* trace bridge
* host-side mirror

### 第四步

补：

* `reflection.py`
* replay regression
* E2E testbot 场景

### 第五步

再评估是否进入：

* `developmental_core`
* endogenous drives v2
* persistent self-model v2

这个顺序跟你现有路线也一致：先 MVS，再 developmental core 深化。

---

## 12. 风险与止损

### 风险 1：鲜活但漂

表现：更像活物，但 identity 经常跳。
修正：提高 `identity_invariants` 更新门槛。

### 风险 2：稳但死

表现：始终一致，但经历无法塑造它。
修正：提高 external_result 权重，强化后果回流。

### 风险 3：情绪文案化

表现：会说"谨慎/焦虑/好奇"，但策略没变化。
修正：测试里强制要求 appraisal 影响 `response_tendency`。

### 风险 4：adapter 偷做本体

表现：EgoCore 为了方便开始自己补 self-model 逻辑。
修正：按边界 Gate 拦截。

### 风险 5：cycle 污染

表现：一次性上下文被误固化为长期 cycle。
修正：提高 promotion 阈值，增加 repeated evidence 条件。

---

## 13. 最终收口

这版草案的核心不是"做出复杂人格系统"，而是：

> **先把 OpenEmotion 做成一个最小、统一、可重放、会被经历塑造的主体更新核；
> 再让 EgoCore 作为唯一正式宿主，把它安全地接进现实世界。**

这正好贴合你当前已经收口的三个前提：

* **MVS 优先，不跳开放发展式自我**
* **EgoCore 外壳 + OpenEmotion 内核**
* **Cycle / replay / deterministic / governance 继续保留为科学仪器层**

下一步最小闭环动作就是：
**先把 `schemas.py + state.py + kernel.py + 5 个最小测试` 写出来。**
