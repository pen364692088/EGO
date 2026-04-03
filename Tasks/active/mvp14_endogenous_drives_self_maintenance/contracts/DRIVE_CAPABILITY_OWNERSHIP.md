# WP9 / MVP14 Drive Capability Ownership

## Purpose

冻结 `WP9/MVP14` 的 capability ownership，防止 drive / maintenance 能力在 `OpenEmotion`、`EgoCore`、compatibility adapter 之间再次形成双真相源或职责偷换。

## Formal Ownership Table

| Capability | Formal owner | Bounded consumer / bridge | Explicit non-owner |
|---|---|---|---|
| endogenous drive state | `OpenEmotion/emotiond/drives/*` | `proto_self_v2` 只可读受治理 drive context | `EgoCore`, `drive_adapter.py`, `drive_homeostasis.py`, `homeostasis.py` |
| drive accumulation / decay / competition | `OpenEmotion/emotiond/drives/*` | runtime mainline downstream consumers | `EgoCore`, legacy drive modules |
| priority snapshot / candidate bias | `OpenEmotion/emotiond/drives/*` | governed prioritization path | transport / delivery surfaces |
| maintenance candidate generation | `OpenEmotion/emotiond/drives/*` | host runtime may schedule only after Governor-compatible bridge | direct transport, direct tool execution |
| self-model owner state | `OpenEmotion/openemotion/self_model/*` | `runtime_summary.self_model_context` | `WP9` drive owner path |
| runtime scheduling / delivery / transport | `EgoCore` | n/a | `OpenEmotion` drives path |
| final reply authority | `EgoCore` | n/a | `OpenEmotion` drives path |
| tool execution authority | `EgoCore` + Governor | n/a | `OpenEmotion` drives path |

## Hard Rules

- `OpenEmotion/emotiond/drives/*` 是 `WP9` formal owner target
- `proto_self_v2` 可以消费 drive context，但不能拥有 drive state
- `drive_adapter.py` 只保留 bounded compatibility / replay-friendly access semantics
- `drive_homeostasis.py` 与 `homeostasis.py` 可以提供测量信号，但不能充当 formal drive owner
- `EgoCore` 可以调度、裁决、投递，但不能伪造或重写 drive owner state

## Forbidden Ownership Drift

- 不把 `drive_adapter.py` 升格为 formal owner
- 不把 `homeostasis.py` 升格为 formal drive state owner
- 不把 `WP8` self-model owner 和 `WP9` drive owner 混成单一状态源
- 不把 transport / reply / tool 权限交给 drive system
