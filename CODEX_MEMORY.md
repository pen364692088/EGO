# CODEX_MEMORY.md

> Codex 开发助手稳定记忆索引
> Source of truth: `.codex/memory/project_truth.jsonl` + `.codex/memory/user_preferences.jsonl`

## 使用边界

- 这套记忆只服务开发助手会话衔接，不接入 EgoCore/OpenEmotion runtime。
- 只保存结构化事实、长期偏好、任务 handoff/closure、session capsule。
- 不保存长聊天原文、未验证结论、调试噪声和过期讨论。

## 新会话注入顺序

1. 当前任务 handoff
2. `CODEX_MEMORY.md`
3. 上一任务 closure
4. 同任务 session capsule

## 稳定项目真相

| ID | 标题 | 来源 | 复核规则 |
|---|---|---|---|
| project-boundary-v1 | EgoCore 与 OpenEmotion 边界 | PROJECT_MEMORY.md#系统边界;docs/AGENT_DEVELOPMENT_PLAYBOOK.md#1 一句话原则 | revalidate_when_boundary_docs_change |
| project-evidence-gate-v1 | 结论强度不得高于证据强度 | PROJECT_MEMORY.md#核心协议;Tasks/templates/gate_acceptance_v1.md#Gate A/B/C 统一验收模板 | revalidate_when_acceptance_rules_change |
| project-execution-env-v1 | 执行环境口径 | PROJECT_MEMORY.md#已验证的关键发现 | revalidate_when_runner_process_changes |
| project-git-publish-v1 | 本仓提交流程 | PROJECT_MEMORY.md#Git 工作流;AGENTS.md#CLAUDE.md - 代码代理专用版 | revalidate_when_git_workflow_changes |
| project-git-shell-default-v1 | Git shell 默认口径 | PROJECT_MEMORY.md#Git 工作流;PROJECT_MEMORY.md#已验证的关键发现 | revalidate_when_git_workflow_changes |
| project-git-index-lock-v1 | Git index.lock 处理口径 | PROJECT_MEMORY.md#已验证的关键发现 | revalidate_when_git_workflow_changes |
| project-closed-loop-workflow-v1 | 默认闭环自审开发流 | PROJECT_MEMORY.md#默认开发闭环;docs/CODEX_CLOSED_LOOP_SELF_REVIEW_WORKFLOW.md | revalidate_when_workflow_contract_changes |
| project-codex-memory-acceptance-v1 | Codex 结构化记忆层新会话验收 | PROJECT_MEMORY.md#已验证的关键发现 | revalidate_when_memory_injection_contract_changes |

## 长期用户偏好

| ID | 标题 | 来源 | 复核规则 |
|---|---|---|---|
| pref-auto-push-remote | 默认自动推送远端 | user_confirmation:2026-03-27:auto_push_remote | until_user_overrides |
| pref-self-review-high | 默认高强度自检 | user_confirmation:2026-03-27:self_review_high;user_confirmation:2026-03-28:closed_loop_self_review | until_user_overrides |
| pref-workflow-layered | 默认分层混合开发流 | user_confirmation:2026-03-27:layered_mixed_workflow;user_confirmation:2026-03-28:closed_loop_self_review | until_user_overrides |
| pref-session-discipline | 保留任务边界新开会话纪律 | user_confirmation:2026-03-27:task_boundary_new_session | until_user_overrides |
| pref-report-four-blocks | 默认四段交付格式 | user_confirmation:2026-03-28:closed_loop_self_review | until_user_overrides |

## 本地目录

- active task records: `.codex/memory/tasks/active/`
- archived closures: `.codex/memory/tasks/archive/`
- session capsules: `.codex/memory/sessions/`

## 维护命令

```bash
python3 scripts/codex_memory.py validate
python3 scripts/codex_memory.py render
python3 scripts/codex_memory.py bootstrap
```
