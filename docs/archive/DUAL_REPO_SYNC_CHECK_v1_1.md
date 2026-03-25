# DUAL_REPO_SYNC_CHECK_v1_1.md

> 检查时间: 2026-03-19T20:10:00Z
> 检查者: CEO agent
> 触发: W3 真相源再对齐

---

## 检查范围

| 文件 | 位置 | 用途 |
|------|------|------|
| PROGRAM_STATE_UNIFIED.yaml | EgoCore/docs/ | 权威状态源 |
| PROGRAM_STATE_UNIFIED.yaml | OpenEmotion/docs/ | 权威状态源 |
| README.md | EgoCore/ | 项目入口文档 |
| README.md | OpenEmotion/ | 项目入口文档 |
| SHIM_REGISTER.md | EgoCore/ | Shim 注册表 |

---

## 检查结果

### 1. 关键状态一致性

| 项目 | EgoCore | OpenEmotion | 一致性 |
|------|---------|-------------|--------|
| CYCLE_CORE_V1 | verified_e2e | verified_e2e | ✅ |
| WS_C1 | verified_e2e | verified_e2e | ✅ |
| ledger_version | 14 | 14 | ✅ |

### 2. Shim 数量一致性

| 来源 | 数量 | 一致性 |
|------|------|--------|
| SHIM_REGISTER.md | 8 | ✅ |
| EgoCore PROGRAM_STATE | 8 | ✅ |
| OpenEmotion PROGRAM_STATE | 8 | ✅ |

### 3. Sync Status 一致性

| 项目 | EgoCore | OpenEmotion | 一致性 |
|------|---------|-------------|--------|
| OpenEmotion_README | aligned | aligned | ✅ |
| OpenEmotion_PROGRAM_STATE | aligned | aligned | ✅ |
| EgoCore_README | aligned | aligned | ✅ |
| EgoCore_PROGRAM_STATE | aligned | aligned | ✅ |

### 4. 主链定义一致性

| 来源 | 主链入口 | 一致性 |
|------|----------|--------|
| EgoCore README | subject_adapter.cycle() | ✅ |
| OpenEmotion README | /cycle endpoint | ✅ |
| DUAL_REPO_MAINLINE.md | subject_adapter.cycle() → /cycle | ✅ |
| SHIM_REGISTER.md | subject_adapter.cycle() | ✅ |

---

## 已修复的口径残差

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| OpenEmotion sync_status | EgoCore_README: needs_update | aligned |
| BOUNDARY:shim_registry 证据 | 4 shims registered | 8 shims registered |
| OpenEmotion README WS_C1 | in_verification | verified_e2e |
| OpenEmotion README long-term self summary | code_exists | verified_e2e |

---

## 当前状态

**README / PROGRAM_STATE / SHIM_REGISTER / 实际目录 四者一致** ✅

---

## 下一步

- W1: C3 观察期执行
- W2: shim 审计
- W4: v1.1.0 删除窗口

---

## 参考

- `docs/PROGRAM_STATE_UNIFIED.yaml` (双仓)
- `docs/DUAL_REPO_MAINLINE.md`
- `SHIM_REGISTER.md`
