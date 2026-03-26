# P7 风险权威冲突报告

## 结论

P7 开始时，正式主链存在真实的 risk authority source 冲突，不能直接假设“只是字段名不统一”。冲突主要发生在 EgoCore 正式 runtime 层，多模块各自维护 message risk 词表/正则/评分逻辑。

## 冲突点

| file | conflict type | pre-P7 problem |
|---|---|---|
| `EgoCore/app/runtime_v2/proto_self_runtime.py` | keyword tables | 自带高/中风险关键词表，并直接生成 risk level |
| `EgoCore/app/runtime/context_assembler.py` | keyword tables | 自带另一套 safety keyword 规则，并决定 approval hint |
| `EgoCore/app/runtime/semantic_router.py` | regex patterns | 自带高风险模式，用于路由保护 |
| `EgoCore/app/runtime/approval_policy.py` | regex patterns | 自带高风险模式，用于审批确认 |

## 冲突风险

- 同一条消息在不同模块得到不同 risk level
- runtime 实际判定与 trace/evidence 解释不一致
- 新增样本时需要同时维护多份词表，极易重新分叉
- OpenEmotion 接收到的 risk signal 可能只是某一份副本的结果，而不是宿主统一裁决

## 收口动作

1. 建立 `EgoCore/app/risk_signal.py` 作为唯一正式 authority。
2. 把 `proto_self_runtime`、`context_assembler`、`semantic_router`、`approval_policy` 改成只消费 canonical source。
3. 删除 `approval_policy` 的本地 message 高风险词表，避免保留最后一份平行 scorer。
4. 把 host->proto-self 桥接统一到 `safety_context.risk_level`。
5. 将 legacy `risk` 与 numeric `risk_level` 降为 compat-only 输入，由 normalizer/schema 吸收。

## 当前状态

| area | status |
|---|---|
| EgoCore message risk scorer | 已统一 |
| Runtime risk field emit | 已统一 |
| Runtime trace/evidence field contract | 已统一到 `risk_level` |
| OpenEmotion host boundary normalization | 已统一 |
| compat input absorption | 已保留并登记 |

## 剩余非冲突项

- `approval_policy` 的高风险路径集合仍存在，但它属于路径边界策略，不是第二套 message risk scorer
- OpenEmotion 其他模块里的数值 `risk` 概念仍存在，但它们属于 EFE/候选动作/资源代价，不是本任务中的 host runtime risk authority

## 判定

本次先识别冲突，再完成收口，满足“若发现多个 risk authority source 并存，必须先给冲突报告”的约束。
