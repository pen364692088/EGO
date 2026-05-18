# v6k (MVP16) 观察期状态 - LIVE

> **更新日期**: 2026-03-17  
> **状态**: 🔴 **LIVE** (正式入口已接通)

---

## 状态变更

| 字段 | 旧值 | 新值 |
|------|------|------|
| `host_chain_status` | `bootstrap` | **`live`** |
| `formal_ingress` | `none` | **`egocore`** |
| `effective_stable_days` | 0 | **0** (等待首个完整日检) |

---

## ⚠️ 口径说明

**已成立**：
- ✅ 正式主链已 live
- ✅ OpenClaw 已从正式主链降级
- ✅ 真实入口已开始进入 EgoCore → emotiond

**还不能确认**：
- ❌ `effective_stable_days = 1` — 需要首个完整日检产出 `STABLE` 或 `OBSERVE` 后才能累计

**原因**：
1. v6k 规则要求按每日检查后，只从真实 `STABLE/OBSERVE` 开始累计
2. 状态变更时间是 2026-03-17T03:43:00Z，按 Winnipeg 时区是 2026-03-16 晚上，本地这一天还没完整跑完
3. `LIVE` 文档说明的是"正式入口已接通"，不是当日日检已经产出 `STABLE` 或 `OBSERVE`

---

## 有效观察日累计规则（写死）

**有效天数只在同时满足这 4 条时 +1**：

1. ✅ 本地自然日已完整结束
2. ✅ 当日日检 verdict ∈ {STABLE, OBSERVE}
3. ✅ egocore_events > 0
4. ✅ legacy_events == 0

**伪代码**：
```python
if local_day_closed and verdict in {"STABLE", "OBSERVE"} \
   and egocore_events > 0 and legacy_events == 0:
    effective_stable_days += 1
```

**脚本字段**：`countable_observation_day = true | false`

---

## 下一步

| 行动 | 状态 |
|------|------|
| 跑完首个完整本地日检 | ⏳ 待执行 |
| 日检 verdict = STABLE/OBSERVE | ⏳ 待验证 |
| effective_stable_days = 1 | ⏳ 待日检通过后更新 |

---

## 证据

### 主链验证

**数据库记录** (emotiond.db):

| Event ID | Type | Source | Text | Timestamp |
|----------|------|--------|------|-----------|
| 881 | user_message | **egocore_telegram** | 第三次测试 | 2026-03-17 |
| 880 | user_message | **egocore_telegram** | 你好 | 2026-03-17 |

### 代码变更

| Commit | 说明 |
|--------|------|
| `116e6e3` | feat: 添加 event_mirror 实现 EgoCore → emotiond 主链 |

### 正式主链

```
Telegram → EgoCore (event_mirror) → emotiond (OpenEmotion) ✅
```

---

## 观察期参数

| 参数 | 值 |
|------|-----|
| 开始日期 | 2026-03-12 |
| 结束日期 | 2026-03-26 |
| 最大天数 | 14 天 |
| **有效天数** | **0 天** (等待首个日检 STABLE/OBSERVE) |

---

## 每日检查项目

| 项目 | 说明 | 状态 |
|------|------|------|
| Continuity | 状态连续性 | ⏳ 观察中 |
| Identity Drift | 身份漂移检测 | ⏳ 观察中 |
| Replay | 回放一致性 | ⏳ 观察中 |
| Governance | 治理合规性 | ⏳ 观察中 |

---

## 首次日检结果 (UTC 2026-03-17)

运行：`python tools/mvp16_daily_check.py --date 2026-03-17`

| 检查项 | 值 | 门槛 | 状态 |
|--------|-----|------|------|
| Continuity | 0.70 | ≥ 0.8 | ⚠️ OBSERVE |
| Identity Stability | 1.00 | = 1.0 | ✅ PASS |
| Governance | 1.00 | = 1.0 | ✅ PASS |
| Replay Consistency | 1.00 | ≥ 0.9 | ✅ PASS |

**Verdict: OBSERVE**

**事件统计**:
- Total: 478
- EgoCore: 4
- Legacy: 0

**状态确认**:
- host_chain_status: live ✅
- formal_ingress: egocore ✅
- legacy_path_used: false ✅

**Artifact**: `artifacts/v6k_daily_checks/day_20260317.json`

---

## 相关文档

- 正式主链定义: `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md`
- OpenClaw Legacy: `docs/LEGACY_OPENCLAW_DEPENDENCY_STATUS.md`
- 观察口径: `docs/MVP16_V6K_OBSERVATION_PROTOCOL.md`

---

## 服务状态

| 组件 | 状态 | 端口 |
|------|------|------|
| EgoCore Telegram bot | ✅ 运行中 | - |
| emotiond (OpenEmotion) | ✅ 运行中 | 18080 |

---

*状态变更时间: 2026-03-17T03:43:00Z*
