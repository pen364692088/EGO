# Layer 3: Proto-Self V2 Dual Repo

```yaml
task_id: L3-20260328-PSK-V2
created_at: "2026-03-28T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: verify_passed
```

---

## 真实目标

在不替换当前 V1 默认主线的前提下，实现 `Proto-Self V2` 的最小双仓纵切：

- OpenEmotion: `proto_self_v2` schema + kernel + trace
- EgoCore: adapter + runtime 显式版本入口 + evidence capture

---

## 成功判据（系统级）

- [ ] `proto_self.v2` contract 已落 repo-tracked 文件
- [ ] OpenEmotion `proto_self_v2` kernel 可调用
- [ ] EgoCore adapter/runtime 可显式进入 V2 路径
- [ ] V2 trace/evidence 能进入宿主审计链
- [ ] 默认 V1 主线未被隐式替换

---

## 当前层级与主链状态

```yaml
current_layer: implementation
main_chain_status: 接入
enabled_status: false
trigger_evidence: targeted repo tests
```

---

## Authority Source

- [PROTO_SELF_KERNEL_V2_IMPLEMENTATION_TASK.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/active/PROTO_SELF_KERNEL_V2_IMPLEMENTATION_TASK.md)
- [PROTO_SELF_KERNEL_V2_SPEC.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/docs/PROTO_SELF_KERNEL_V2_SPEC.md)
- [PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md)
- [AGENT_DEVELOPMENT_PLAYBOOK.md](/mnt/d/Project/AIProject/MyProject/Ego/docs/AGENT_DEVELOPMENT_PLAYBOOK.md)

---

## 双仓分工

| 组件 | 所属仓 | 核心修改 | 接口变动 |
|------|--------|----------|----------|
| Proto-Self V2 schema/kernel | OpenEmotion | `openemotion/proto_self_v2/` | `proto_self.v2` |
| V2 contract | EgoCore | `contracts/proto_self_v2.schema.json` | ingress contract |
| Adapter/runtime | EgoCore | `app/openemotion_adapter/proto_self_adapter.py` / `app/runtime_v2/proto_self_runtime.py` | v1/v2 分流 |
| Replay/evidence | Dual | trace/evidence 消费 | `proto_self.trace.v2` |

---

## 六问门禁

| 问题 | EgoCore | OpenEmotion | 结论 |
|------|---------|-------------|------|
| 这个能力归谁？ | ingress / runtime / evidence |主体语义 / kernel / trace | 双仓联动 |
| 权威源是谁？ | adapter/runtime contract | V2 canonical spec | 单一 authority |
| 和哪个模块耦合？ | `proto_self_adapter.py` / `proto_self_runtime.py` | `proto_self_v2/*` | 明确 |
| 是否引入双重真相源？ | 禁止 | 禁止 | 只允许桥接，不允许双主 |
| 是否让 shim 变长期黑箱？ | 不允许 | 不允许 | 仅 bounded bridge |
| 失败由谁兜底？ | 回退 V1 默认入口 | 保留 V2 代码不启用 | 可回退 |

---

## 实施顺序

1. OpenEmotion 落 `proto_self_v2` schema/kernel/trace
2. EgoCore 落 adapter/runtime version routing + contract file
3. 双仓补最小测试
4. 跑主链最小 evidence
5. 通过后再把状态推进到 `published`

---

## 当前进度

- [x] OpenEmotion `proto_self_v2` schema/kernel/trace 已落
- [x] EgoCore adapter/runtime version routing 已落
- [x] contract 文件已落
- [x] 最小 repo tests 已通过
- [ ] 真实 runtime E4 evidence 未补
- [ ] 远端发布未完成

---

## 回退计划

| 场景 | 回退动作 |
|------|----------|
| V2 contract 不稳 | 保留代码，停用入口 |
| adapter/runtime 分流异常 | 默认回退到 v1 |
| replay/evidence 不闭环 | 不提升完成口径 |
