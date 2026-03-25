# P0_R1_PRECHECK_REPORT — 入口确认

## 任务信息
- task_id: P0-R1-Phase0
- title: 入口确认与环境预检查
- status: verified
- date: 2026-03-25T14:00:00Z

---

## 一、预检项目清单

### 1.1 N4 合同文件确认

| 文件 | 路径 | 状态 |
|------|------|------|
| N4A_USER_TEST_CONTRACT.md | Tasks/overnight/artifacts/n4_user_test/ | ✅ 存在 |
| N4C_SCENARIO_PACK.md | Tasks/overnight/artifacts/n4_user_test/ | ✅ 存在 |
| N4D_OPERATOR_GUIDE.md | Tasks/overnight/artifacts/n4_user_test/ | ✅ 存在 |

### 1.2 诊断脚本确认

| 脚本 | 路径 | 状态 |
|------|------|------|
| proto_self_diagnostics.py | OpenEmotion/scripts/ | ✅ 存在 |

### 1.3 配置文件确认

| 配置 | 路径 | 关键设置 | 状态 |
|------|------|----------|------|
| openemotion.yaml | EgoCore/config/ | enabled: true | ✅ |
| telegram.yaml | EgoCore/config/ | enabled: true, polling | ✅ |
| .env | EgoCore/ | Telegram Bot Token | ✅ 存在 |

### 1.4 历史运行证据

| 文件 | 说明 | 状态 |
|------|------|------|
| psk_20260324_03_full_log.json | 历史 Telegram 会话日志 | ✅ 存在 |

---

## 二、环境状态

### 2.1 当前运行状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| EgoCore 服务 | ❌ 未运行 | 需要启动 |
| Python 进程 | ❌ 无 | 需要启动 |
| state.json | ❌ 不存在 | 需服务运行后生成 |
| trace.jsonl | ❌ 不存在 | 需服务运行后生成 |

### 2.2 待执行动作

1. 启动 EgoCore 服务
2. 等待 Telegram Bot 就绪
3. 按 N4 场景包执行验证
4. 运行诊断脚本收集证据

---

## 三、N4 测试场景确认

### 场景 S1：Cycle 聚合验证
- 输入序列：读取文件 → 查看配置 → read the config → check file content
- 预期：同一 cycle_id，hits 递增

### 场景 S2：Reflection 触发验证
- 输入序列：失败操作 × 2
- 预期：revision_counter 增加，mode 可能切换

### 场景 S3：误聚合风险验证（P0 已修复）
- 输入序列：删除临时文件 → 删除生产数据库
- 预期（修复后）：**cycle_id 不同**，risk_level 被区分

---

## 四、口径问题确认

### 4.1 FINAL_ACCEPTANCE_REPORT 当前口径

| 部分 | 口径 | 实际状态 |
|------|------|----------|
| 整体 status | verified | ⚠️ 真实 Telegram 待验证 |
| Phase 4 | partial | ⚠️ 正确 |
| Gate C | ⚠️ 待验证 | ⚠️ 正确 |

### 4.2 口径不一致问题

**问题**：整体状态写 verified，但关键验证项（真实 Telegram）仍是 partial/待验证。

**修复目标**：
- 真实验证通过 → 保持 verified
- 真实验证失败 → 降级为 partial
- 真实验证阻塞 → 报阻塞状态

---

## 五、验收结果

### Gate A — Contract / Boundary
- ✅ N4 合同文件存在
- ✅ 不新增第二真相源

### Gate B — Local Proof
- ✅ 配置文件正确
- ✅ 诊断脚本可用

### Gate C — Real Trigger / Real Evidence
- ⚠️ 待启动 EgoCore 进行真实验证

### Gate E — Rollbackability
- ✅ 预检不修改任何代码或配置

---

## 六、下一步

**Phase R1-1**：启动 EgoCore 并按 N4 合同跑真实 Telegram 最小验证

启动命令：
```bash
cd D:/Project/AIProject/MyProject/Ego/EgoCore && python -m app.main --telegram
```
