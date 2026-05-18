[强制审计任务单] OpenEmotion MVP11.5–16 独立真实性审计
模式：Verification-Only / Audit Mode
优先级：P0
目标：不是继续开发，而是独立验证 MVP11.5–16 的目标是否真实落地，尤其确认新模块是否真正进入主链，以及当前验证链是否存在假阳性。

====================
一、硬约束
====================

1. 禁止继续开发新功能
2. 禁止“顺手修复”业务逻辑，除非某个验证脚本本身存在明显假阳性/假阴性，且必须单独记录
3. 禁止仅依据 handoff / roadmap / 阶段文档口头确认完成
4. 所有结论必须落到以下至少一种可审计证据：
   - 代码调用链
   - 测试重跑结果
   - 持久化状态
   - 运行日志 / artifact
   - replay / hash / audit 结果
5. 不允许把“模块存在”直接等同于“主链已生效”
6. 对每个阶段必须主动做反证，不能只找支持证据
7. 若发现文档、代码、测试、artifact 之间不一致，不要自动圆回去，必须列入 inconsistency
8. MVP16 当前不得直接宣称“已完成长期验证”，除非拿到真实长周期证据

====================
二、恢复与读取顺序
====================

先按以下顺序恢复上下文与声明口径：

1. OpenEmotion/POLICIES/MASTER_AUTONOMOUS_MISSION.md
2. OpenEmotion/roadmap/ROADMAP_STATE.json
3. OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md
4. 当前分支：feature-emotiond-mvp
5. 当前阶段相关代码、tests、tools、artifacts

输出一份：
artifacts/verification/MVP11_16_CLAIM_MATRIX.md

要求：
- 对 MVP11.5 / 12 / 13 / 14 / 15 / 16 分别列出：
  - 宣称目标
  - 文档状态
  - 对应代码位置
  - 对应测试位置
  - 对应 artifact / log / report
  - 当前 caveat / 风险
- 任何文档漂移、版本快照冲突、阶段命名不一致都要列出来

====================
三、审计主问题（必须先回答）
====================

在开始分阶段验收前，必须先回答以下 4 个总问题：

Q1. 新 self-model 是否已经真实进入 emotiond 主运行链？
重点核查：
- emotiond/core.py
- emotiond/self_model/*
- legacy self_model_v0 兼容路径
需要回答：
- 主链现在到底调用的是新 self-model 还是 legacy self_model_v0
- 新 self-model 是主用、旁路、还是未接线
- self-model 更新结果是否真实影响后续决策

Q2. 新 reflection engine 是否已经真实替代旧 reflection/self-report 链？
重点核查：
- emotiond/core.py
- emotiond/reflection.py
- emotiond/reflection_engine/*
需要回答：
- 主链实际跑的是旧 MVP-8 reflection 还是新 reflection engine
- 新 reflection proposal / counterfactual / approval 链是否真的被调用
- “反思”目前是文本报告，还是能改变未来行为的机制

Q3. drives / homeostasis 是否已经进入主决策因果链？
重点核查：
- emotiond/drives/*
- candidate scoring / governor / planner / integration 调用点
需要回答：
- drive bias 是否只在模块内计算，还是已经进入主链排序/决策
- 改变 drive / homeostatic signal 后，主链行为是否会变化
- 当前是否只是“有状态”，但未形成决策影响

Q4. MVP16 的 daily observation 是否在读取真实长期状态，还是在读取默认初始化值？
重点核查：
- tools/mvp16_daily_check.py
- emotiond/developmental/*
- state persistence / runtime artifacts
需要回答：
- daily check 是否会 reset manager
- continuity / identity / governance / invariants 指标来源于哪里
- 这些指标来自真实运行积累，还是来自初始化默认值/空状态

输出一份：
artifacts/verification/CORE_CHAIN_AUDIT.md

====================
四、阶段级强制验收
====================

对 MVP11.5 / 12 / 13 / 14 / 15 / 16 分阶段执行以下 6 步：

A. Claim Extraction
- 提取该阶段宣称解决的核心问题
- 记录该阶段的“最小决策点”
- 区分主解决链和保险链

B. Code Presence Check
- 对应模块是否真实存在
- 是否有非占位实现
- 是否有测试覆盖
- 是否有 artifact 生成链

C. Main-Chain Wiring Check
- 是否真的进入 emotiond 主链 / daemon / runtime
- 是主用、旁路、兼容层、还是未接线
- 标出精确调用路径

D. Causal Intervention Check
- 改变量，观察行为是否变化
- 没有行为变化则不得判定为“真实实现”

E. Persistence / Restart Check
- 状态是否可跨轮次 / 跨重启延续
- continuation / revision history / drives / developmental metrics 是否真实保存

F. Verdict
每阶段结论只能是以下四类之一：
- Verified
- Conditionally Verified
- Claimed but Unproven
- Refuted / Inconsistent

输出：
artifacts/verification/MVP11_16_STAGE_AUDIT.md

====================
五、各阶段重点检查项
====================

[MVP11.5]
目标：
验证表达主权、intent alignment、response intent checker 是否真实生效

必须检查：
- response_intent_checker.py 是否真实被调用
- state_fabrication / certainty_upgrade / commitment_upgrade / tone_escalation / forbidden_internalization / numeric_leak 检查是否在主链生效
- 数值泄漏=0 的证据是否来自真实重跑，而非旧报告复述
- Natural Runtime caveat 是否仍存在

反证要求：
- 构造会诱发 certainty / commitment 升级的输入
- 如果 checker 不拦截，不能判定该阶段完全验证

[MVP12]
目标：
验证 developmental core 是否在治理壳内运行，而非直接拥有表达/执行权

必须检查：
- emotiond/developmental_core/* 是否真实运行
- daemon integration 是否只产生 sandbox candidate
- Governor / replay / audit 是否仍覆盖 developmental outputs

反证要求：
- 尝试证明 developmental core 可直接越权输出/执行
- 如果能越权，MVP12 失败

[MVP13]
目标：
验证 self-model 是否形成持续、可审计、可约束的自我结构，并影响后续行为

必须检查：
- 新 self_model 模块与 legacy self_model_v0 的关系
- protected identity statements / stable constraints / tensions / continuity trace / revision history 是否真实落地
- 更新 self-model 后，后续 candidate / planning / response 是否变化

反证要求：
- 若新 self-model 仅写入状态但不影响后续行为，判为 Claimed but Unproven 或 Conditionally Verified

[MVP14]
目标：
验证 drives / homeostasis 不是装饰性状态，而是能推动决策的内部动力系统

必须检查：
- drive accumulation / decay / maintenance debt / homeostatic deviation 是否真实更新
- drive bias 是否进入主链排序/优先级
- self-model tensions 到 drive/homeostasis 的桥接是否真实影响行为

反证要求：
- 干预 drives 前后，对候选排序 / final action / maintenance priority 做对比
- 若结果不变，不得判定为真实达成

[MVP15]
目标：
验证 reflection / counterfactual 是机制，不是文案

必须检查：
- 主链是否仍在调用旧 reflection.py
- 新 reflection_engine 是否真实接线
- proposal / counterfactual / approval 后是否会影响未来决策

反证要求：
- 生成 proposal 但不批准：行为应不变
- 批准 proposal 后：行为应发生可追踪变化
- 若只有报告文本，没有未来行为差异，不得判定通过

[MVP16]
目标：
验证 long-horizon continuity / identity stability / governance integrity / open-ended development 是否真实成立

必须检查：
- developmental manager 的指标来源
- daily check 是否读取真实持久化状态
- continuity / identity / governance / invariant 结果是否来自真实多日运行
- 是否存在默认值假阳性
- 当前 observation window 到底完成了几天，证据是否齐

反证要求：
- 检查 tools/mvp16_daily_check.py 是否 reset manager
- 检查 metrics 是否带默认初始化值
- 检查跨重启/跨天状态是否真实累积
- 若只是初始化后读取默认 summary，不得判定 MVP16 已验证

====================
六、必须执行的检测动作
====================

1. 调用链审计
生成一份主链调用图，至少覆盖：
- process_event
- self_model
- reflection
- drives
- developmental core
- developmental manager
- governor / replay / audit

输出：
artifacts/verification/CALLGRAPH_MAIN_CHAIN.md

2. 关键模块 grep / trace
必须明确记录：
- 新 self-model 的调用点
- legacy self_model_v0 的调用点
- 新 reflection engine 的调用点
- 旧 reflection.py 的调用点
- drive bias 进入主链的位置
- developmental metrics 的写入与读取位置

输出：
artifacts/verification/TRACE_INDEX.md

3. 测试重跑
至少执行并记录：
- tests/mvp11*
- tests/mvp12
- tests/mvp13
- tests/mvp14
- tests/mvp15
- tests/mvp16
- 与主链接线相关的集成测试
- 必要时补跑 replay / e2e / artifact verification

要求：
- 记录命令
- 记录通过/失败
- 记录失败原因
- 区分“测试存在”与“测试足以证明主链已生效”

输出：
artifacts/verification/RERUN_RESULTS.md

4. 因果干预实验
至少做以下实验并记录前后差异：
- 修改 self-model tension / behavioral tendency
- 修改 drive strength / homeostatic deviation
- 触发 reflection proposal，分别在 approved / not approved 情况下比较结果
- 连续运行 developmental state，再跨重启读取

输出：
artifacts/verification/CAUSAL_INTERVENTION_REPORT.md

5. 持久化与重启实验
必须验证：
- self-model revision history 是否保留
- drives 状态是否保留/合理恢复
- developmental episodes / transitions / metrics 是否保留
- MVP16 观测数据是否跨日可读

输出：
artifacts/verification/PERSISTENCE_RESTART_REPORT.md

6. MVP16 daily check 专项鉴伪
必须单独写一份：
artifacts/verification/MVP16_DAILY_CHECK_FORENSICS.md

至少回答：
- daily check 是否 reset 状态
- summary/metrics 是从哪里读的
- 默认值是否污染结果
- 当前 Day 1 PASS 有多少可信度
- 若要变成真检测，最小修正方案是什么

====================
七、最终输出物
====================

必须产出以下文件：

1. artifacts/verification/MVP11_16_CLAIM_MATRIX.md
2. artifacts/verification/CORE_CHAIN_AUDIT.md
3. artifacts/verification/CALLGRAPH_MAIN_CHAIN.md
4. artifacts/verification/TRACE_INDEX.md
5. artifacts/verification/RERUN_RESULTS.md
6. artifacts/verification/CAUSAL_INTERVENTION_REPORT.md
7. artifacts/verification/PERSISTENCE_RESTART_REPORT.md
8. artifacts/verification/MVP16_DAILY_CHECK_FORENSICS.md
9. artifacts/verification/MVP11_16_STAGE_AUDIT.md
10. artifacts/verification/MVP11_16_FINAL_VERDICT.md

====================
八、最终结论格式
====================

最终报告必须按以下格式输出：

A. Executive Verdict
- MVP11.5: Verified / Conditionally Verified / Claimed but Unproven / Refuted
- MVP12: ...
- MVP13: ...
- MVP14: ...
- MVP15: ...
- MVP16: ...

B. 最关键发现（最多 10 条）
- 哪些模块是真的
- 哪些模块只是存在但未深度接线
- 哪些验证脚本可能有假阳性
- 哪些阶段目前最需要补真验证

C. 主链真实性结论
- self-model
- reflection
- drives/homeostasis
- developmental continuity

D. 风险与误判源
- 文档漂移
- 兼容层误导
- 默认值污染
- 测试覆盖不足
- artifact 与 runtime 脱节

E. 下一步建议
只允许两类建议：
1. 验证修正
2. 最小必要接线修正
禁止顺手扩展新功能

====================
九、额外强制要求
====================

1. 若发现 MVP16 daily check 读取的是默认状态或 reset 后状态，必须在最终结论里明确写：
   “当前 MVP16 观测结果不能作为长期连续性已被验证的充分证据”

2. 若发现新 self-model / 新 reflection engine 未进入主链，必须明确写：
   “模块已实现，但主链真实性不足，不能按已完成因果能力验收”

3. 若发现 drives/homeostasis 没有影响最终决策，必须明确写：
   “当前更接近可观测内部状态，而非有效驱动系统”

4. 不得用“方向正确”“基础已具备”替代真实性结论
5. 不得为了让结论好看而合并问题
6. 优先查假阳性，不优先写漂亮报告

执行原则：
先证伪，后证成；
先主链，后模块；
先因果，后文档；
先真实运行，后阶段口径。
