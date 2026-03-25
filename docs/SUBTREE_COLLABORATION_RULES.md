
# 《EGO 总仓 subtree 协作与更新规则》强执行文档

## 0. 文档目的

本文件用于固定 **EGO 总仓 + 双 subtree** 的正式协作规则，避免后续出现以下问题：

* 把 subtree 当普通目录乱改
* 把总仓当成双核真实来源，形成双重真相源
* 不清楚该在 `Ego`、`EgoCore`、`OpenEmotion` 哪一层改代码
* `subtree pull / push` 流程混乱，导致历史污染或边界漂移

本规则的目标不是“Git 操作方便”，而是：

* 保持 **EgoCore = 唯一正式宿主**
* 保持 **OpenEmotion = 唯一正式主体内核**
* 保持 **EGO = 集成总仓 / 编排总仓 / 交付总仓**
* 保持单一权威源，不制造双主

---

## 1. 当前层级

当前层级：**仓库治理层 / 集成编排层**

当前正式结构：

```text
EGO/
├─ EgoCore/        # subtree
├─ OpenEmotion/    # subtree
├─ Tasks/
├─ scripts/
├─ AGENTS.md
├─ CLAUDE.md
└─ README.md
```

---

## 2. 正式归属

### 2.1 三层角色定义

#### EGO

正式定位：**总仓 / 集成仓 / 编排仓 / 对外交付仓**

负责：

* 汇总项目入口
* 管理双核接入关系
* 管理跨仓脚本、任务、集成说明、总 README
* 管理演示、部署编排、统一验收说明
* 作为 subtree 集成承载层

不负责：

* 承载 EgoCore 本体实现真相源
* 承载 OpenEmotion 本体实现真相源
* 把 subtree 当普通复制目录长期直接开发

#### EgoCore

正式定位：**唯一正式宿主**

负责：

* 用户交互
* runtime
* tool execution
* safety / governance / audit
* 对 OpenEmotion 的结构化接线与宿主适配

#### OpenEmotion

正式定位：**唯一正式主体内核**

负责：

* identity
* self-model
* memory evolution
* appraisal
* reflection
* proto-self / subject state / developmental internals

---

## 3. 权威源规则

## 硬规则：任何关键能力只能有一个权威源

### 3.1 权威源定义

* **EgoCore 相关实现** 的权威源：`EgoCore` 源仓
* **OpenEmotion 相关实现** 的权威源：`OpenEmotion` 源仓
* **总仓集成、编排、跨仓说明** 的权威源：`EGO` 总仓

### 3.2 明确禁止

禁止以下情况：

1. 在 `EGO/EgoCore/` 改了宿主代码，但不回到 EgoCore 源仓治理，长期让总仓副本变成真实源
2. 在 `EGO/OpenEmotion/` 改了主体代码，但不回到 OpenEmotion 源仓治理
3. 在 `EGO` 根目录新建一套与 EgoCore / OpenEmotion 职责重复的正式实现
4. 把 subtree 副本当成“另一个正式源”
5. 文档写一套、仓库结构跑一套，形成双重真相

---

## 4. 日常开发主流程

## 默认主方案：**源仓开发，总仓集成**

这是唯一默认主流程。

### 4.1 EgoCore 相关开发

若需求属于以下范围：

* runtime
* bridge
* delivery
* tool execution
* host policy
* safety / governance
* channel integration

则必须去 **EgoCore 源仓** 开发，而不是优先在 `EGO/EgoCore/` 里直接改。

标准流程：

1. 进入 EgoCore 源仓
2. 完成开发与测试
3. 提交并推送到 EgoCore 远程
4. 回到 EGO 总仓执行：

```bash
git subtree pull --prefix=EgoCore ego-core <branch> --squash
```

5. 在 EGO 总仓提交集成记录

### 4.2 OpenEmotion 相关开发

若需求属于以下范围：

* identity
* self-model
* memory evolution
* appraisal
* reflection
* proto-self kernel
* subject state / reflection logic

则必须去 **OpenEmotion 源仓** 开发。

标准流程：

1. 进入 OpenEmotion 源仓
2. 完成开发与测试
3. 提交并推送到 OpenEmotion 远程
4. 回到 EGO 总仓执行：

```bash
git subtree pull --prefix=OpenEmotion open-emotion <branch> --squash
```

5. 在 EGO 总仓提交集成记录

---

## 5. 总仓允许修改的内容

以下内容允许直接在 `EGO` 总仓修改：

* 根目录 `README.md`
* 总体架构说明
* 集成说明
* subtree 协作规则
* `Tasks/`
* `scripts/`
* 跨仓编排脚本
* CI / 集成验证脚本
* 只属于总仓层的治理文档
* 不改变子仓本体权威源归属的 glue code / orchestration code

---

## 6. 总仓禁止直接长期承载的内容

以下内容**不得默认在 EGO 总仓直接长期开发**：

### 6.1 本应属于 EgoCore 的实现

例如：

* runtime 核心逻辑
* Telegram / host / tool 主链
* tool execution policy
* 宿主裁决核心

### 6.2 本应属于 OpenEmotion 的实现

例如：

* appraisal reducer
* reflection engine
* self-model schema
* subject memory evolution
* identity persistence logic

### 6.3 原则

若某实现一旦成熟后应归属于某子仓，则不得长期滞留在总仓根层。

---

## 7. 特殊例外规则

## 只允许两类例外

### 7.1 临时止血修复

允许在 `EGO/EgoCore/` 或 `EGO/OpenEmotion/` 中做临时修补，但必须满足：

* 明确标注为临时修补
* 立即或尽快回迁到对应源仓
* 不得长期停留成为事实权威源

### 7.2 集成验证性修改

若为了验证 subtree 集成链路、总仓 CI、部署编排，需要对子目录做一次性验证修改，可以临时进行；但验证完成后必须：

* 回迁到源仓
* 或回滚
* 或明确归档为实验性操作

---

## 8. subtree 更新规则

## 8.1 默认只用 pull，不默认用 push

默认更新方向：

* 从 `EgoCore` 源仓 → `EGO/EgoCore`
* 从 `OpenEmotion` 源仓 → `EGO/OpenEmotion`

命令模板：

```bash
git subtree pull --prefix=EgoCore ego-core <branch> --squash
git subtree pull --prefix=OpenEmotion open-emotion <branch> --squash
```

### 原因

因为项目当前正式语义是：

* 子仓是本体权威源
* 总仓是集成承载层

所以默认应当“源仓下行到总仓”，而不是“总仓反推覆盖源仓”。

---

## 8.2 subtree push 只作为例外

只有在以下条件同时满足时，才允许使用 `subtree push`：

1. 修改确实发生在总仓子目录中
2. 修改内容明确归属于对应子仓
3. 已确认不会覆盖掉源仓更新
4. 已人工检查 diff
5. 这是例外，不是日常主流程

命令模板：

```bash
git subtree push --prefix=EgoCore ego-core <branch>
git subtree push --prefix=OpenEmotion open-emotion <branch>
```

### 风险提示

`subtree push` 容易把总仓中的临时集成性改动误推回源仓，因此默认不作为常规协作链。

---

## 9. 分支与提交规则

### 9.1 默认分支不得脑补

执行 subtree pull/push 前，先确认真实默认分支，不得想当然写死 `main`。

例如先查：

```bash
git remote show ego-core
git remote show open-emotion
```

### 9.2 总仓提交信息建议

推荐格式：

```text
chore(integration): pull EgoCore subtree from <branch>
chore(integration): pull OpenEmotion subtree from <branch>
chore(monorepo): sync subtree states
docs(governance): update subtree collaboration rules
```

### 9.3 子仓提交信息

仍按各自源仓规范执行，不由总仓覆盖。

---

## 10. 验收规则

以下情况才能报告“subtree 更新完成”：

### A. pull 成功执行

例如：

```bash
git subtree pull --prefix=EgoCore ego-core <branch> --squash
```

输出成功，无冲突或已正确解决冲突。

### B. 目录状态正常

```bash
git status
```

无异常未处理冲突。

### C. 变更归属清晰

能明确说明：

* 本次更新来自哪个源仓
* 来自哪个分支
* 更新的是哪一层能力
* 是否影响总仓脚本或文档

### D. 留有真实证据

至少保留：

* subtree pull/push 命令
* git status
* git log --oneline -n 10

---

## 11. 冲突处理规则

若 subtree pull 出现冲突：

1. 先停止继续堆补丁
2. 明确冲突属于哪一层：

   * 源仓真实实现冲突
   * 总仓临时修改污染
   * 集成脚本与子仓实现耦合冲突
3. 优先恢复“权威源优先”原则
4. 不允许为了图快直接把总仓副本当作最终真相源覆盖过去

### 冲突处置优先级

1. 确认权威源
2. 保留权威源正确实现
3. 重新适配总仓 glue / script / doc
4. 最后再做集成提交

---

## 12. 文档同步规则

只要 subtree 结构、协作规则、边界归属发生变化，至少同步以下文档：

* `README.md`
* 总仓治理文档
* 主索引文档
* 边界说明文档
* 开发/集成说明

禁止仓库结构已变化、文档仍按旧双仓模式表述。

---

## 13. 对 Claude / Agent 的执行要求

执行涉及 subtree 的任务时，必须先判断任务归属：

### 属于 EGO 总仓的任务

可直接在总仓处理：

* README
* docs
* Tasks
* scripts
* CI/integration
* cross-repo glue

### 属于 EgoCore 的任务

不得默认在总仓根层或总仓副本中长期实现，应回源仓处理后再 subtree pull。

### 属于 OpenEmotion 的任务

不得默认在总仓根层或总仓副本中长期实现，应回源仓处理后再 subtree pull。

---

## 14. 禁止性规则

以下行为禁止：

1. 把 `EGO/EgoCore` 或 `EGO/OpenEmotion` 当成随手长期开发主场
2. 不经过归属判断，直接在总仓里改子仓核心实现
3. subtree pull 前不查分支
4. subtree 冲突后继续盲修
5. 把临时止血修补报成正式长期完成
6. 把集成副本当作真实权威源
7. 在未提供真实命令输出前声称“subtree 已更新完成”
8. 在未接主链、未形成真实 pull/push 证据前声称“闭环完成”

---

## 15. 当前正式推荐工作方式

## 主方案

**EGO 总仓负责集成；EgoCore / OpenEmotion 源仓负责本体开发。**

这是当前最稳、最贴合边界、最不容易制造双主的方案。

## 备选

在总仓子目录里做极少量临时修补，再有纪律地回迁源仓。
这只能作为过渡方案，不得变成长期常态。

---

## 16. 最小执行模板

### 更新 EgoCore 到总仓

```bash
git subtree pull --prefix=EgoCore ego-core <branch> --squash
git status
git log --oneline -n 10
```

### 更新 OpenEmotion 到总仓

```bash
git subtree pull --prefix=OpenEmotion open-emotion <branch> --squash
git status
git log --oneline -n 10
```

### 总仓推送

```bash
git push origin <current-branch>
```

---

## 17. 收口口径

满足以下条件时，才可表述为：

**“EGO 总仓 subtree 集成链已生效”**

条件包括：

* 总仓存在且远程已配置
* 子仓 subtree 关系真实存在
* subtree pull 已验证
* 权威源归属清晰
* 协作规则已文档化

未满足时，只能表述为：

* “已完成结构接入，待协作规则固化”
* “已实现 subtree，但长期协作链待验证”
* “已集成，待真实同步演练”

---

