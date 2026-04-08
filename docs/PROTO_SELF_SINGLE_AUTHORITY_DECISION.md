# Proto-Self / MVP12-15 单一权威源决策

> 这是 prescriptive decision layer，不是新的 authority source。
>
> 代码证据基线见 [PROTO_SELF_MVP_AUTHORITY_AUDIT.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/PROTO_SELF_MVP_AUTHORITY_AUDIT.md)；当前主权威仍是 `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`，并由当前 README / logic flow 补充。

## 当前 formal mainline

当前 formal mainline 固定为：

- `EgoCore/app/openemotion_hooks/native_hooks.py`
- `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
- `OpenEmotion/openemotion/proto_self_v2/kernel.py`

当前结构不是“纯 v2 小核”，而是：

- `proto_self_v2` = 当前 formal surface / orchestrator
- `proto_self` v1 = 当前 active substrate
- `openemotion/* formal owner packages` = owner state + governed writeback target

## A. Unique Authority Table

| capability | formal owner | active substrate | compat/shim | reference-only | single-authority decision |
|---|---|---|---|---|---|
| `identity invariants` | `openemotion.proto_self.state.IdentityInvariants` | `openemotion.proto_self.kernel` + `openemotion.proto_self.reducers` | 无 | `openemotion.identity.identity_invariants`, `openemotion.identity.long_term_self_summary` | 当前唯一 runtime authority 维持在 v1 substrate；identity formal owner 暂不接主链，按 reference-only 处理 |
| `self-model` | `openemotion.self_model/*` | `openemotion.proto_self.self_model` + v1 `SelfModel` state | `OpenEmotion/emotiond/self_model_adapter.py` (deleted) | `OpenEmotion/emotiond/self_model_mirror.py` (deleted) | formal owner 是唯一 authority；legacy adapter/mirror 已物理删除，不再作为 live-ish blocker |
| `drives / appraisal` | `openemotion.endogenous_drives/*` | `openemotion.proto_self.appraisal` + v1 `DriveField` | 无 | 无新增 reference-only | formal owner 是唯一 authority；v1 substrate 保留为 active compute/proposal layer，不再叙述成 authority |
| `reflection / structured revision` | `openemotion.reflective_self/*` | `openemotion.proto_self.reflection` | 无 | `OpenEmotion/emotiond/reflection_adapter.py`, `OpenEmotion/emotiond/reflection_shadow.py`, `OpenEmotion/emotiond/reflection_engine/*`, `OpenEmotion/emotiond/reflection.py`, `OpenEmotion/emotiond/self_counterfactual.py` | formal owner 是唯一 authority；v1 `reflection_note` 只保留 transient trigger 语义，不再叙述成 structured revision authority |

### 当前必须明确的结论

- 当前仍由 v1 substrate 承担的能力：
  - `identity invariants`
  - `self-model` 的 base delta 计算
  - `drives / appraisal` 的 base delta 计算
  - `reflection` 的 lightweight trigger / `reflection_note`
- 当前只是名义 owner、尚未真正接入 formal mainline 的能力：
  - `openemotion.identity.identity_invariants`
  - `openemotion.identity.long_term_self_summary`

## B. Keep / Downgrade / Reference-only / Delete-candidate Table

| path_or_group | decision | reason |
|---|---|---|
| `EgoCore/app/runtime_v2/proto_self_runtime.py` | 保留 | 当前 formal mainline host bridge，负责 runtime projection 与 governed writeback |
| `EgoCore/app/openemotion_adapter/proto_self_adapter.py` | 保留 | 当前 formal mainline adapter；双核边界桥接点 |
| `OpenEmotion/openemotion/proto_self_v2/*` | 保留 | 当前 formal mainline surface / orchestrator |
| `OpenEmotion/openemotion/proto_self/*` 中当前 formal mainline 可达部分 | 保留 | 当前 active substrate；仍承担 identity/self-model/drives/reflection base semantics |
| `OpenEmotion/openemotion/self_model/*` | 保留 | 当前 self-model formal owner |
| `OpenEmotion/openemotion/endogenous_drives/*` | 保留 | 当前 drives formal owner |
| `OpenEmotion/openemotion/reflective_self/*` | 保留 | 当前 reflection / structured revision formal owner |
| `OpenEmotion/emotiond/self_model_adapter.py` | deleted | 已物理删除；history 仅保留在 cleanup ledger / archive report |
| `EgoCore/app/openemotion_adapter/proto_self_restore.py` | 降级为 compat/shim | restore helper，不是当前 formal recovery path |
| `OpenEmotion/openemotion/identity/identity_invariants.py` | reference-only | formal owner 名义存在，但当前未接 formal mainline |
| `OpenEmotion/openemotion/identity/long_term_self_summary.py` | reference-only | support library 存在，但当前未接 formal mainline |
| `OpenEmotion/emotiond/self_model_mirror.py` | deleted | 已物理删除；history 仅保留在 cleanup ledger / archive report |
| `OpenEmotion/openemotion/cycle_core/*` | reference-only | 历史 cycle implementation reference，不在当前 formal mainline |
| `OpenEmotion/emotiond/memory_legacy.py` | reference-only | 历史 memory residue，不在当前 formal mainline |
| `OpenEmotion/emotiond/reflection_adapter.py` | reference-only | 历史 reflection guidance 参考面，不是当前 reflection authority |
| `OpenEmotion/emotiond/reflection_shadow.py` | reference-only | 历史 shadow 观察面，不是当前 reflection authority |
| `OpenEmotion/emotiond/reflection_engine/*` | reference-only | 历史 reflection engine 参考面，不是当前 formal mainline |
| `OpenEmotion/emotiond/reflection.py` | reference-only | 历史 reflection support residue，不是当前 reflection authority |
| `OpenEmotion/emotiond/self_counterfactual.py` | reference-only | 历史 counterfactual support residue，不是当前 reflection authority |
## C. Minimum Change Plan

### 1. Decision Layer

- 产出本决策文档
- 明确四类能力的：
  - formal owner
  - active substrate
  - compat/shim
  - reference-only
- 明确：
  - `proto_self_v2` 是 formal surface，不是这四类能力各自的 owner
  - `emotiond.developmental_core` 不在本轮处理范围内

### 2. Public Surface

- 同步：
  - `OpenEmotion/README.md`
  - `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
  - `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
  - `docs/CAPABILITY_REGISTRY.md` 的生成源与输出
- 消除两类误导：
  - 把名义 owner 写成 live owner
  - 把 substrate / shim / mirror 写成 authority

### 3. Drift Gate

- 新增静态 verifier：
  - `scripts/codex/verify_proto_self_single_authority.py`
- 接入：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- gate 只做静态一致性检查，不跑 runtime

## 下一步最小删改动作

1. 先冻结这四类能力的 authority 口径，不再允许 README / logic flow / register 自相矛盾。
2. 若未来继续推进删除 admission，只保留仍未完成收口的 compat/shim 残留路径，不再把已经物理删除的 `self_model_adapter / self_model_mirror` 当作 blocker。

## Final Fate

- `OpenEmotion/emotiond/self_model_adapter.py` 已物理删除
- `OpenEmotion/emotiond/self_model_mirror.py` 已物理删除
- 这两条路径不再属于 current blocker / compat consumer / live-ish blocker

3. `identity invariants` 若将来要真正收口到 formal owner，必须另开任务，把 `openemotion.identity.identity_invariants` 接进 mainline；本轮不做这件事。
