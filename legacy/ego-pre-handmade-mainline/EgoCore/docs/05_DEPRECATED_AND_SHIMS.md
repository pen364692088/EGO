# 05_DEPRECATED_AND_SHIMS.md

> 本文件是当前 repo 的 path classification register。它登记正式路径、compatibility-only 路径、reference-only 路径与 deprecated-candidate。
>
> 它不是新的 authority source；正式边界与主链仍以 `README.md`、`EgoCore/README.md`、`OpenEmotion/README.md`、`docs/CURRENT_PROJECT_LOGIC_FLOW.md`、`EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml` 为准。

## 分类规则

| classification | 含义 | claim ceiling |
|---|---|---|
| `formal` | 当前正式主链或正式 owner surface | 可作为当前正式入口引用 |
| `compatibility_only` | 仍保留以兼容旧链、旧测试或降级路径，但不是当前正式主链 | 不得叙述成“也算正式主链的一部分” |
| `reference_only` | 只保留作技术参考、历史对照、镜像或兼容资料 | 不得当成 runtime authority 或当前 owner |
| `deprecated_candidate` | 看起来可退役，但还缺删除前提或引用清零证明 | 不等于现在就可删 |

## 当前登记

| path_or_module | classification | owner | existence_reason | formal_replacement | claim_ceiling | exit_condition | risk |
|---|---|---|---|---|---|---|---|
| `EgoCore/app/runtime_v2/*` | `formal` | `EgoCore` | 当前 Telegram/CLI 正式 runtime 主链 | 无 | 当前正式宿主 runtime | 无 | 主链误删 |
| `EgoCore/app/telegram_bot.py` 中 `use_runtime_v2` 路径 | `formal` | `EgoCore` | 当前 Telegram 正式入口 | 无 | 当前正式 Telegram 主线 | 无 | 主线误改 |
| `EgoCore/app/telegram_bot.py` 中 `_handle_with_new_runtime` | `compatibility_only` | `EgoCore` | 保留旧 runtime/new runtime 兼容路径与显式降级面 | `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery` | 仅兼容/降级路径，不是当前正式主链 | 旧兼容测试与旧入口依赖清零后再评估删除 | 误回漂成双主 |
| `EgoCore/app/telegram_bot.py` 中 `_handle_with_legacy_router` | `deprecated_candidate` | `EgoCore` | 更早 Telegram 路由路径残留 | Runtime v2 Telegram path | 不是正式主链，只能作为历史兼容候选 | 无主链引用 + 兼容测试移除 + 删除风险复验 | 删除后旧路径失效 |
| `EgoCore/app/runtime/agent_runner.py` | `compatibility_only` | `EgoCore` | 旧 runtime core 与历史执行链兼容 | `EgoCore/app/runtime_v2/*` | 仅旧链兼容，不是当前主 runtime | 旧 runtime 路径与测试进一步迁走 | 历史功能断裂 |
| `EgoCore/app/runtime/request_classifier.py` | `compatibility_only` | `EgoCore` | 旧 request 分类与 host override 残留 | Runtime v2 + bridge | 仅兼容旧路径，不拥有当前意图解释权 | 旧 runtime 链不再依赖 | host override 回归 |
| `EgoCore/app/runtime/request_registry.py` | `compatibility_only` | `EgoCore` | 旧 request lifecycle registry 残留 | Runtime v2 session/runtime state | 仅兼容旧路径，不拥有当前 request 生命周期权威 | 旧 runtime 测试迁移完成 | 链路回归 |
| `OpenEmotion/emotiond/drive_adapter.py` | `compatibility_only` | `OpenEmotion` | drives/appraisal 兼容投影 helper | `OpenEmotion/openemotion/endogenous_drives/*` | 只是 formal owner 的 bounded projection helper，不是第二套实现 | formal owner 已有 live consumer 且 legacy caller 清零后再评估进一步收缩 | 恢复历史兼容 helper 文案 |
| `OpenEmotion/emotiond/drives/*` | `compatibility_only` | `OpenEmotion` | drives 兼容 re-export wrapper surfaces | `OpenEmotion/openemotion/endogenous_drives/*` | 只是 thin compat re-export surfaces，不是 authority | formal owner 稳定且 wrapper caller 清零后再评估进一步收缩 | 恢复历史 wrapper 文案 |
| `EgoCore/prompts/AGENT.md` | `formal` | `EgoCore` | 当前 Runtime v2 文件式 prompt | 无 | 当前正式 prompt surface | 无 | prompt 误改 |
| `EgoCore/prompts/SOUL.md` | `formal` | `EgoCore` | 当前 Runtime v2 文件式 prompt | 无 | 当前正式 prompt surface | 无 | prompt 误改 |
| `EgoCore/prompts/TOOLS.md` | `formal` | `EgoCore` | 当前 Runtime v2 文件式 prompt | 无 | 当前正式 prompt surface | 无 | prompt 误改 |
| `EgoCore/app/runtime_v2/prompt_files.py` | `formal` | `EgoCore` | 当前文件式 prompt loader | 无 | 当前正式 prompt loader | 无 | prompt surface 失效 |
| `OpenEmotion/openemotion/*` | `formal` | `OpenEmotion` | 当前正式主体本体与 formal owner 实现 | 无 | 当前正式主体本体实现 | 无 | 主体本体误删 |
| `OpenEmotion/emotiond/*` | `reference_only` | `OpenEmotion` | 历史服务/宿主处理面、迁移参考与残留支撑 | `OpenEmotion/openemotion/*` + EgoCore 正式宿主主链 | 不是当前 formal owner，也不是当前 Telegram 主链 | 当前残余引用与历史文档完成切分后再评估收缩 | 服务/历史链说明失真 |
| `OpenEmotion/legacy/openclaw/*` | `deprecated_candidate` | `OpenEmotion` | 历史 OpenClaw 依赖残留 | EgoCore + OpenEmotion 正式双核 | 不是正式主链，只能作为历史残留候选 | 无引用确认 + 替代确认 | 误删后历史链测试断裂 |
| `OpenEmotion/openclaw_skill/*` | `reference_only` | `OpenEmotion` | 兼容 OpenClaw skill 形态的参考面 | EgoCore + OpenEmotion 正式双核 | 不是 formal owner，不是当前 runtime authority | 确认无人使用后再删 | 兼容链断裂 |
| `OpenEmotion/openemotion/identity/identity_invariants.py` | `reference_only` | `OpenEmotion` | 名义 identity owner surface，当前未接 formal mainline | `OpenEmotion/openemotion/proto_self/state.py` + `OpenEmotion/openemotion/proto_self/kernel.py` | 当前不能叙述成 live runtime authority | 若未来真接入 formal mainline，再重新分类 | 被误当 live identity owner |
| `OpenEmotion/openemotion/identity/long_term_self_summary.py` | `reference_only` | `OpenEmotion` | support library，当前未接 formal mainline | 当前无 formal replacement；仅保留 support/reference 角色 | 当前不能叙述成 live runtime authority | formal consumer 明确后再重分类 | 被误当 live long-term self owner |
| `OpenEmotion/openemotion/cycle_core/*` | `reference_only` | `OpenEmotion` | 历史 cycle implementation reference | `OpenEmotion/openemotion/proto_self/*` + `proto_self_v2/*` | 不是当前 formal mainline | formal caller 清零已确认后再评估收缩 | 被误当当前 cycle authority |
| `OpenEmotion/emotiond/memory_legacy.py` | `reference_only` | `OpenEmotion` | 历史 memory residue / 对照面 | `OpenEmotion/openemotion/proto_self/*` + future formal memory owner wiring | 不是当前正式 memory owner | formal caller 清零 + 删除 admission 通过 | 被误当当前记忆 authority |
| `OpenEmotion/emotiond/reflection_adapter.py` | `reference_only` | `OpenEmotion` | 历史 reflection guidance 兼容面 | `OpenEmotion/openemotion/reflective_self/*` + `OpenEmotion/openemotion/proto_self/reflection.py` | 不是当前 reflection authority | formal caller 清零 + 删除 admission 通过 | 被误当当前 reflection authority |
| `OpenEmotion/emotiond/reflection_shadow.py` | `reference_only` | `OpenEmotion` | 历史 reflection shadow 观测面 | `OpenEmotion/openemotion/reflective_self/*` | 不是当前 reflection authority | formal caller 清零 + 删除 admission 通过 | 被误当当前 reflection authority |
| `OpenEmotion/emotiond/reflection_engine/*` | `reference_only` | `OpenEmotion` | 历史 reflection engine 参考面 | `OpenEmotion/openemotion/reflective_self/*` | 不是当前 reflection authority | formal caller 清零 + 删除 admission 通过 | 被误当当前 reflection authority |
| `OpenEmotion/emotiond/reflection.py` | `reference_only` | `OpenEmotion` | 历史 reflection support residue | `OpenEmotion/openemotion/reflective_self/*` + `OpenEmotion/openemotion/proto_self/reflection.py` | 不是当前 reflection authority | formal caller 清零 + 删除 admission 通过 | 被误当当前 reflection authority |
| `OpenEmotion/emotiond/self_counterfactual.py` | `reference_only` | `OpenEmotion` | 历史 counterfactual support residue | `OpenEmotion/openemotion/reflective_self/*` | 不是当前 reflection authority | formal caller 清零 + 删除 admission 通过 | 被误当当前 reflection authority |

## 已删除

- `OpenEmotion/emotiond/self_model_adapter.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger
- `OpenEmotion/emotiond/self_model_mirror.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger
- `EgoCore/app/openemotion_adapter/proto_self_restore.py`：已物理删除，历史 proof/archive evidence 仅保留在 cleanup ledger

## 当前收口期约束

- 当前 repo 处于**边界冻结下的收口期**：
  - 不再改双核边界
  - 不再换 Telegram 正式主链
  - 不把 compat/reference 路径重新叙述成“也算主线”
- 任何公开入口提到 compat/reference 路径时，都必须同时承认：
  - 它不拥有当前 authority
  - 它不等于正式主链
  - 它有明确退出条件或保留理由

## 使用规则

- `compatibility_only` 不等于“当前也推荐改这里”
- `reference_only` 不等于“当前 runtime 还会主动走到这里”
- `deprecated_candidate` 不等于“现在就能删”
- `active substrate` 也不等于 authority；单一权威收口以 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 为准
- 只有在“引用清零 + 替代稳定 + 删除风险复验”后，才允许从 register 移除

## 生成 / 对齐依赖

补证或核对时优先参考：

- `README.md`
- `EgoCore/README.md`
- `OpenEmotion/README.md`
- `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
- `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`
- `scripts/codex/verify_path_classification.py`
