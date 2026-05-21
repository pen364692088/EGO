# 快速启动指南

## 选择模板的决策树

```
任务来了
  │
  ├─ 5分钟内能完成？
  │   ├─ YES → layer1_quick_fix.md
  │   └─ NO →
  │       │
  │       ├─ 涉及 EgoCore + OpenEmotion 两个仓库？
  │       │   ├─ YES → layer3_dual_repo.md
  │       │   └─ NO →
  │       │       │
  │       │       ├─ 涉及边界/权限争议？
  │       │       │   ├─ YES → layer3_boundary_fix.md
  │       │       │   └─ NO → layer2_functional.md
  │       │       │
  │       │       └─ 结束
  │       │
  │       └─ 结束
  │
  └─ 结束
```

---

## 创建任务的 3 步法

### Step 1: 复制模板

```bash
# 根据决策树选择模板
cp Tasks/templates/layer2_functional.md Tasks/active/20260323-L2-func-parser-fix.md
```

### Step 2: 填充必填字段

打开文件，填写以下内容：

```yaml
# 文件头部（必须）
task_id: L2-20260323-001
owner: "你的名字"
status: pending
```

```markdown
# 真实目标（必须）
修复 semantic_parser 中的 parser_source 污染问题
```

```markdown
# 成功判据（必须，可验证的）
- [ ] parser_source 在三条路径上严格保真
- [ ] timeout 不回退到错误的 source
```

### Step 3: 开始执行

根据模板中的闭环推进，每完成一个阶段更新状态：

1. `Spec`
2. `Author`
3. `Self-Reviewer`
4. `Independent Reviewer`
5. `Verifier`
6. `Publisher`

---

## 使用示例

### 示例 1: 紧急修复（Layer 1）

```bash
cp Tasks/templates/layer1_quick_fix.md Tasks/active/20260323-L1-fix-typo.md
```

编辑 `20260323-L1-fix-typo.md`：

```yaml
task_id: L1-20260323-001
owner: "claude"
status: spec_ready
```

```markdown
## 真实目标
修复 README.md 中的拼写错误

## 成功判据
- [ ] typo 已修正
- [ ] 无其他改动

## 修改点
| 文件 | 行号 | 修改 | 原因 |
|------|------|------|------|
| README.md | 45 | s/拼写错误/正确拼写/ | typo |
```

Spec → Author → Self-Reviewer → Independent Reviewer（可选）→ Verifier → Publisher

---

### 示例 2: 功能实现（Layer 2）

```bash
cp Tasks/templates/layer2_functional.md Tasks/active/20260323-L2-func-semantic-parser.md
```

编辑并填充：

```yaml
task_id: L2-20260323-002
owner: "claude"
layer: 2
type: functional
target_repo: EgoCore
status: spec_ready
```

```markdown
## 真实目标
收窄 heuristic 回退职责，修复 parser_source 保真

## 成功判据
- [ ] heuristic 不再使用执行动词列表
- [ ] parser_source 三条路径保真
- [ ] E2E 验证通过

## 当前层级
current_layer: implementation
main_chain_status: planning
```

按阶段执行：
1. **Spec** → 写清 authority source、成功判据、最小验收路径
2. **Author** → 做最小可验证主线修正
3. **Self-Reviewer** → findings-first 自 review
4. **Independent Reviewer** → 高风险任务启用独立 reviewer subagent
5. **Verifier** → 跑最低门与对应回归
6. **Publisher** → 只在 `review_passed + verify_passed` 后提交与推送

---

### 示例 3: 双仓联动（Layer 3）

```bash
cp Tasks/templates/layer3_dual_repo.md Tasks/active/20260323-L3-dual-proto-v2.md
```

编辑并填充基本信息，然后：

```yaml
# 规划者完成任务后
HANDOFF:
  from: "规划者"
  to: "OpenEmotion 实现者"
  status: READY_FOR_OPENEMOTION_IMPL
```

派发 subagent：

```python
Agent(
    description="PSK v2 OpenEmotion 实现",
    prompt="读取 Tasks/active/20260323-L3-dual-proto-v2.md，完成 Stage 2...",
    isolation="worktree"
)
```

实现者完成后更新 HANDOFF，继续下一阶段。

---

## 任务状态流转

```
pending
  ↓
spec_ready
  ↓
author_done
  ↓
review_passed
  ↓
verify_passed
  ↓
published
  ↓
  ├─ blocked（遇到阻塞）→ 添加 blocked_by → 解决后恢复
  ├─ handed_off（如需接力）→ 填写 HANDOFF 区
  ↓
archived（移动到 Tasks/archive/）
```

---

## 关键原则

1. **Persist first**：先写文档，再汇报
2. **One task one file**：一个任务一个文档
3. **Update as you go**：边做边更新，不要最后补
4. **Handoff clear**：交接时必须填写 HANDOFF 区
5. **Grade honestly**：方案等级如实标注（formal/transitional/temporary）
6. **Findings first**：自 review 和 verify 先写发现项，再给通过结论
7. **High-risk double review**：Telegram 主链、双仓、状态恢复、evidence 任务默认启用独立 Reviewer subagent

---

## 命名速查

| 类型 | 命名示例 |
|------|----------|
| Layer 1 快速修复 | `20260323-L1-fix-typo-readme.md` |
| Layer 2 功能实现 | `20260323-L2-func-parser-source.md` |
| Layer 3 双仓联动 | `20260323-L3-dual-proto-v2.md` |
| Layer 3 边界修复 | `20260323-L3-boundary-adapter-fix.md` |
| 排障 | `20260323-TROUBLESHOOT-timeout-issue.md` |
| 设计 | `20260323-DESIGN-memory-v2.md` |
| 验收 | `20260323-VERIFY-parser-e2e.md` |
