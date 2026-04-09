# Claim Language Policy

本文件约束公开入口文档的人类可读口径，不新增 authority source。

## 当前权威状态（2026-04-09）

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- 当前 formal mainline 仍是：`telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 这是 repo/integration scope closeout，不是 real-channel 新效果声明
- thin substrate / compat / reference-only 残留仍存在，但不阻塞 closeout
- 剩余项仅保留在 `optional housekeeping / future cleanup backlog`

## 当前正式口径

- 本文件只约束公开入口文档的人类可读口径，不升格为 authority source
- 当前 closeout 口径已统一到 README / logic flow / capability / acceptance / scripts / claim 文档首页
- 这里的规则仍用于防止把 controlled axis、bounded influence、proposal discipline 误说成 live authority

## repo_authority_cleanup

- `repo_authority_cleanup: closeout-complete (repo/integration scope)`
- closeout 的含义是 repo/integration scope 的边界与验证完成，不是把所有 historical helper / thin substrate 一刀切删除
- 剩余项仅作为 `optional housekeeping / future cleanup backlog`

## 当前权威入口

- [PROGRAM_STATE_UNIFIED.yaml](PROGRAM_STATE_UNIFIED.yaml)
- [STATUS.md](STATUS.md)
- [../README.md](../README.md)
- [CURRENT_PROJECT_LOGIC_FLOW.md](CURRENT_PROJECT_LOGIC_FLOW.md)
- [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md)
- [ACCEPTANCE_CHAINS.md](ACCEPTANCE_CHAINS.md)
- [EXPERIENCE_SCRIPTS.md](EXPERIENCE_SCRIPTS.md)
- [codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md](codex/tasks/repo-authority-cleanup/CLOSEOUT_REPORT.md)

## 历史与详细证据入口

- 下方 policy 规则保留为公开口径约束，不是新的 authority source
- 具体 current state / current logic / closeout proof 仍以对应文档为准

## 禁止宽口径的条件

若某能力处于以下任一状态，禁止描述成“已经体现自我意识”“已经有主观能动性”“已经具备完整自我”“已经会自主表达”：

- `maintenance_mode`
- `proposal_only`
- `behavioral_authority = none`
- `feature flag off`
- `allowlist only`
- `host-governed`

## 允许口径

- 在 controlled axis 上已验证……
- 在 formal owner + controlled observation 轴上成立……
- 当前只证明 bounded influence / writeback / continuity / proposal discipline
- 不证明 direct reply authority / tool authority / transport authority
- 不证明 unrestricted autonomy
- 不证明 philosophical consciousness

## 适用范围

- `README.md`
- `EgoCore/README.md`
- `OpenEmotion/README.md`
- `docs/CURRENT_PROJECT_LOGIC_FLOW.md`
- `docs/TELEGRAM_FLOW_VIEW_README.md`
- `docs/CAPABILITY_REGISTRY.md`
- `docs/ACCEPTANCE_CHAINS.md`
- `docs/EXPERIENCE_SCRIPTS.md`
