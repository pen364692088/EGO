# OpenEmotion 仓库分支与发布规约 v1

> 状态：生效 
> 适用仓库：OpenEmotion 
> 目标：建立**单一真相链、可控发布链、低分支债务**的仓库协作方式，避免阶段分支长期并存、主线失真、发布口径漂移。

---

## 1. 规约结论

OpenEmotion 仓库从本版本起，采用如下治理结构：

- `main`：**稳定发布主线**
- `feature-emotiond-mvp`：**当前开发主线**
- 其他分支一律视为**短期工作分支**
- 阶段性成果不再长期保留 `feature/v6x-*` 这类里程碑分支
- 里程碑记录通过 **tag + 文档 + artifact** 保留，不通过长期活跃分支保留

本规约的核心目标不是"分支更少"，而是：

> **让 OpenEmotion 始终只有一条开发真相链和一条发布真相链。**

---

## 2. 仓库治理目标

本规约解决以下历史问题：

1. 阶段分支过多，难以判断哪条是当前真相
2. `main` 长期落后，失去"稳定主线"意义
3. 相同能力链在多个分支重复存在，增加 merge / 回溯成本
4. 阶段能力（如 v6b~v6g）长期停留在分支而非主线
5. 发布、文档、测试、artifact 口径容易漂移

本规约追求的结果是：

- 开发主线清晰
- 发布主线可信
- 分支生命周期短
- 阶段成果可追溯
- 合并路径固定
- 删除分支安全有据

---

## 3. 分支模型

## 3.1 长期分支

### 3.1.1 `main`
定义：

- 稳定发布主线
- 对外默认查看分支
- 仅承接**已完成收口且通过验证**的能力链
- 不承接零散实验、未完成阶段工作、未验收分支

职责：

- 保存当前公开稳定状态
- 作为 tag / release 的基线
- 作为回滚与对账的参考线

约束：

- 禁止直接在 `main` 上开发
- 禁止直接 force-push
- 禁止将多个阶段分支直接逐个合入 `main`
- 原则上只允许从 `feature-emotiond-mvp` 或受控修复分支合入

---

### 3.1.2 `feature-emotiond-mvp`
定义：

- 当前开发主线
- OpenEmotion 的**唯一开发真相链**
- 所有阶段成果最终必须回到这里

职责：

- 承接短期工作分支的合并结果
- 维护当前完整能力链
- 作为合入 `main` 的唯一正常来源

约束：

- 不允许长期保留与其并行的"阶段真相链"
- 所有短期开发最终都必须回收到这里
- 若某阶段成果未收口回本分支，则视为未完成

---

## 3.2 短期分支

除 `main` 和 `feature-emotiond-mvp` 外，其他分支一律视为短期分支。

适用类型：

- 功能实现
- 缺陷修复
- 实验验证
- 治理收口
- 文档修正

命名规范：

- `task/<topic>`
- `fix/<topic>`
- `spike/<topic>`
- `chore/<topic>`

示例：

- `task/quality-signal-provenance`
- `task/complex-semantic-reasoning-rollout`
- `fix/readme-main-sync`
- `spike/auto-mode-evaluation`
- `chore/test-fixture-cleanup`

约束：

- 必须从 `feature-emotiond-mvp` 切出
- 完成后必须尽快合回并删除
- 不得长期停留为"半正式主线"
- 不得承担阶段里程碑的长期保存职责

---

## 3.3 禁止再使用的分支模式

以下模式自本规约起默认禁止长期存在：

- `feature/v6b-*`
- `feature/v6c-*`
- `feature/v6d-*`
- `feature/v6e-*`
- `feature/v6f-*`
- `feature/v6g-*`

原因：

这类分支本质是**阶段快照分支**，不是独立产品线。 
长期保留只会导致：

- 真相链分裂
- 历史线堆积
- 修复难以归位
- 发布口径混乱

阶段结果应保留为：

- tag
- 文档
- report
- artifact

而不是长期活跃分支。

---

## 4. 开发流程规约

## 4.1 新功能开发流程

标准流程：

1. 从 `feature-emotiond-mvp` 切出短期分支
2. 在短期分支完成实现、测试、文档
3. 通过验证后合回 `feature-emotiond-mvp`
4. 删除短期分支
5. 达到稳定收口标准后，再由 `feature-emotiond-mvp` 合入 `main`

标准示意：

```text
feature-emotiond-mvp
 └── task/xxx
 └── merge back into feature-emotiond-mvp
 └── later merge into main
```

---

## 4.2 禁止的开发路径

以下路径禁止：

### 禁止路径 A

直接在 `main` 上开发

原因：

- 破坏稳定主线
- 增加回滚与审计成本

### 禁止路径 B

短期分支直接合入 `main`

原因：

- 绕过开发主线
- 容易把未充分收口内容打进稳定线

### 禁止路径 C

多个阶段分支分别直接合入 `main`

原因：

- 会让 `main` 含有混乱历史
- 破坏"单一开发真相 → 稳定发布真相"的结构

### 禁止路径 D

长期保留"已经完成但未回主线"的阶段分支

原因：

- 相当于把主线外包给临时分支
- 时间越久，收口成本越大

---

## 5. 合并策略规约

## 5.1 合并到 `feature-emotiond-mvp`

适用对象：

- 短期工作分支
- 已完成验证的受控改动

默认要求：

- 优先使用保留语义清晰的 merge 方式
- 避免无意义重复 merge
- 必须确认 docs / tests / artifacts 同步

建议：

- 普通短期分支：可用常规 merge
- 多提交但只代表一个工作单元的分支：可考虑 squash
- 含阶段收口语义时：建议保留收口节点

---

## 5.2 合并到 `main`

合并 `main` 的前提必须全部满足：

1. `feature-emotiond-mvp` 已完成阶段收口
2. 主链测试通过
3. 文档完整
4. 关键文件完整
5. 无未解决冲突残留
6. 合并目的明确：**同步稳定状态，而非暂存开发中状态**

默认方式：

```bash
git checkout main
git pull origin main
git merge --no-ff origin/feature-emotiond-mvp
```

要求：

- 保留一次清晰的"开发主线 → 稳定主线"收口节点
- 合并后必须重新验证
- 合并前建议打保护 tag

---

## 5.3 阶段分支收口规则

如果未来又出现一条连续能力链，例如：

- `task/a`
- `task/b`
- `task/c`

收口时遵循：

### 优先规则

若某最新分支已经完整包含前序链路，优先一次性收口最新超集分支。

### 禁止规则

不要为了"看起来完整"把所有阶段分支都 merge 一遍。

收口前必须先做：

- merge-base 审计
- 独有提交审计
- 文件完整性审计
- 测试验证

---

## 6. 发布与 Tag 规约

## 6.1 Tag 的职责

Tag 用于记录：

- 阶段里程碑
- 主线收口点
- 发布基线
- 合并前保护点

Tag 不是可选项，而是替代长期阶段分支的关键手段。

---

## 6.2 Tag 类型

### A. 保护 Tag

用于大规模 merge / cleanup 前的保护点。

示例：

- `pre-merge-main-20260316-165102`
- `pre-merge-mvp-20260316-165102`

### B. 里程碑 Tag

用于记录正式阶段完成状态。

示例：

- `openemotion-v6g-consolidated`
- `openemotion-mvp-memory-chain-v1`

### C. 发布 Tag

用于标记对外稳定版本。

示例：

- `v0.1.0`
- `v0.2.0-beta`

---

## 6.3 Tag 使用规则

- 重大合并前必须打保护 tag
- 开发主线收口进 `main` 后，建议打里程碑 tag
- 对外可引用状态必须有 tag
- 不允许只靠 commit hash 承载长期里程碑口径

---

## 7. 分支保护规约

## 7.1 需要保护的分支

必须保护：

- `main`
- `feature-emotiond-mvp`

---

## 7.2 建议保护规则

### `main`

建议：

- 禁止 force-push
- 禁止直接 push（若平台允许）
- 只允许通过受控 merge / PR 更新
- 合并前必须通过测试
- 合并前必须完成文档与 artifact 对账

### `feature-emotiond-mvp`

建议：

- 禁止 force-push
- 必须通过核心测试后再合入短期分支结果
- 不允许作为长期实验垃圾场

---

## 8. 发布前验证规约

任何准备合入 `main` 的变更，至少必须满足以下验证：

### 必测项

- `pytest -q`
 或
- `pytest -q tests/embedding tests/e2e`

### 必查项

- 关键模块文件完整
- 关键 docs 存在
- 关键 artifact/report 存在
- 分支祖先关系清晰
- 无未说明冲突解决

### 必答项

- 这次为什么能进 `main`
- 这次进 `main` 后，`main` 代表什么稳定状态
- 是否需要打 tag
- 是否需要删除已完成短期分支

---

## 9. 分支删除规约

## 9.1 允许删除的分支

以下分支可删除：

- 已合并且验证通过的短期分支
- 已被最新超集分支吸收的阶段分支
- 不再作为活跃开发分支的历史分支

---

## 9.2 删除前提

删除远端分支前必须确认：

1. 内容已进入 `feature-emotiond-mvp` 或 `main`
2. 相关测试通过
3. 无未迁移文件
4. 无未保留的历史价值
5. 如有里程碑价值，已用 tag / 文档 / artifact 保留

---

## 9.3 删除后要求

删除后必须复核：

- 远端分支列表是否干净
- 是否只保留长期分支与当前活跃短期分支
- 文档中是否仍引用已删除分支名
- CI / README / 指引中是否仍依赖已删除分支

---

## 10. 文档与 Artifact 同步规约

任何进入 `feature-emotiond-mvp` 或 `main` 的阶段成果，不仅是代码，还必须同步以下内容：

- docs
- scripts
- tests
- artifacts / reports
- 必要的 config snapshot

禁止出现：

- 代码进了主线，文档还在阶段分支
- 测试进了主线，artifact 没同步
- report 声称通过，但主线没有对应代码

---

## 11. README 与主线说明规约

README 必须明确说明：

- 当前默认稳定分支：`main`
- 当前开发主线：`feature-emotiond-mvp`
- 日常开发应从 `feature-emotiond-mvp` 切短期分支
- 阶段里程碑通过 tag 与 docs 查询，不通过历史阶段分支查询

若 README 与主线实际状态冲突，必须在最近一次主线收口时同步修正。

---

## 12. 未来版本迭代建议

从 v1 规约生效起，推荐采用以下节奏：

### 日常开发

- 在 `feature-emotiond-mvp` 上持续迭代
- 每个工作单元使用短期分支

### 阶段收口

- 每一阶段完成后先收口到 `feature-emotiond-mvp`
- 确认稳定后再合入 `main`

### 发布节奏

- `main` 每次更新都应对应一个清晰稳定状态
- 重要节点必须打 tag

---

## 13. 违规判定

出现以下任一情况，视为违反本规约：

1. 直接在 `main` 上开发
2. 长期保留阶段分支作为事实主线
3. 短期分支直接绕过 `feature-emotiond-mvp` 合入 `main`
4. 重大合并不打保护 tag
5. 收口后不删短期/阶段分支
6. 文档、测试、artifact 与主线不同步
7. 主线已更新但 README / 使用说明仍指向旧分支
8. 让 `main` 再次长期失真

---

## 14. 当前生效后的仓库口径

自本规约生效起，OpenEmotion 当前仓库口径为：

### 长期分支

- `main`
- `feature-emotiond-mvp`

### 阶段成果记录方式

- tag
- docs
- reports
- artifacts

### 标准开发方式

- 从 `feature-emotiond-mvp` 切短期分支
- 完成后合回 `feature-emotiond-mvp`
- 验证通过后再同步到 `main`

---

## 15. 一句话规约

> **OpenEmotion 永远只允许一条开发真相链和一条发布真相链；阶段成果靠收口、tag 和文档保存，不靠长期阶段分支保存。**
