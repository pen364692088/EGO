# v6k (MVP16) 观察期口径纠偏

> **文档版本**: 1.0.0  
> **创建日期**: 2026-03-17  
> **状态**: 正式生效

---

## 1. 纠偏背景

根据《去 OpenClaw 依赖纠偏 + EgoCore 直连 emotiond 强制执行任务单》，v6k 观察期口径需要调整：

- **正式主链**: EgoCore → emotiond (OpenEmotion)
- **非正式路径**: OpenClaw 扩展、配置、链路验证

**原则**: 只有通过 EgoCore 正式入口的请求，才能计入有效观察天数。

---

## 2. 观察期定义

### 2.1 观察窗口

| 参数 | 值 |
|------|-----|
| 开始日期 | 2026-03-12 |
| 结束日期 | 2026-03-26 |
| 最大天数 | 14 天 |

### 2.2 每日检查项目

| 项目 | 说明 |
|------|------|
| Continuity | 状态连续性 |
| Identity Drift | 身份漂移检测 |
| Replay | 回放一致性 |
| Governance | 治理合规性 |

---

## 3. 新增观察字段

### 3.1 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `host_chain_status` | enum | `bootstrap` \| `live` |
| `formal_ingress` | enum | `egocore` \| `none` |
| `legacy_path_used` | boolean | 是否使用了 legacy 路径 |
| `effective_stable_days` | number | 有效稳定天数 |

### 3.2 有效天数计算规则

**只有同时满足以下条件，才计入有效观察天数**:

1. `host_chain_status = live`
2. `formal_ingress = egocore`
3. `legacy_path_used = false`

**公式**:
```
effective_stable_days = COUNT(
    days WHERE 
        host_chain_status = 'live' 
        AND formal_ingress = 'egocore' 
        AND legacy_path_used = false
)
```

---

## 4. 状态定义

### 4.1 host_chain_status

| 状态 | 说明 | 有效天数 |
|------|------|----------|
| `bootstrap` | 真实入口未接通，空转状态 | ❌ 不计入 |
| `live` | 真实 EgoCore 入口已接通 | ✅ 可计入（需满足其他条件） |

### 4.2 formal_ingress

| 状态 | 说明 | 有效天数 |
|------|------|----------|
| `egocore` | 请求来自 EgoCore 正式入口 | ✅ 可计入 |
| `none` | 无正式入口请求 | ❌ 不计入 |

### 4.3 legacy_path_used

| 值 | 说明 | 有效天数 |
|-----|------|----------|
| `true` | 使用了 OpenClaw 扩展或其他 legacy 路径 | ❌ 不计入 |
| `false` | 仅使用 EgoCore → emotiond 正式主链 | ✅ 可计入 |

---

## 5. 检查脚本更新

### 5.1 新增字段输出

每日检查脚本 `tools/mvp16_daily_check.py` 应输出：

```json
{
  "date": "2026-03-17",
  "continuity": 0.82,
  "identity_stability": 1.0,
  "governance": 1.0,
  "host_chain_status": "bootstrap",
  "formal_ingress": "none",
  "legacy_path_used": false,
  "effective_stable_days": 0,
  "verdict": "BOOTSTRAP"
}
```

### 5.2 状态模板

**BOOTSTRAP 状态**:
```json
{
  "host_chain_status": "bootstrap",
  "formal_ingress": "none",
  "legacy_path_used": false,
  "effective_stable_days": 0,
  "message": "真实 EgoCore 入口未接通，等待正式入口启动"
}
```

**LIVE 状态**:
```json
{
  "host_chain_status": "live",
  "formal_ingress": "egocore",
  "legacy_path_used": false,
  "effective_stable_days": 1,
  "message": "正式主链运行中，有效观察天数 +1"
}
```

---

## 6. 观察期验收标准

### 6.1 有效天数要求

- 最小有效天数: **10 天**（14 天窗口内）
- 连续有效天数: ≥ 7 天

### 6.2 指标门槛

| 指标 | 门槛 |
|------|------|
| Continuity | ≥ 0.8 |
| Identity Stability | = 1.0 |
| Governance | = 1.0 |
| Legacy Path Used | = false (100%) |

---

## 7. 禁止的错误做法

| 禁止行为 | 原因 |
|---------|------|
| 把 BOOTSTRAP 天数计入有效观察天 | 未满足正式入口条件 |
| 把 OpenClaw 触发的请求记为 formal_ingress | OpenClaw 已降级为 legacy |
| 在 legacy_path_used = true 时计入有效天数 | 违反主链定义 |

---

## 8. 状态更新记录

| 日期 | host_chain_status | formal_ingress | legacy_path_used | effective_stable_days |
|------|-------------------|----------------|------------------|----------------------|
| 2026-03-12 | bootstrap | none | false | 0 |
| 2026-03-13 | bootstrap | none | false | 0 |
| 2026-03-14 | bootstrap | none | false | 0 |
| 2026-03-15 | bootstrap | none | false | 0 |
| 2026-03-16 | bootstrap | none | false | 0 |
| 2026-03-17 | bootstrap | none | false | 0 |

**注意**: 以上状态将在真实 EgoCore Telegram 入口启动后更新为 `live`。

---

## 9. 下一步行动

| 优先级 | 行动 | 状态 |
|--------|------|------|
| P0 | 启动 EgoCore Telegram bot | 待执行 |
| P0 | 确认真实请求进入主链 | 待执行 |
| P1 | 更新 host_chain_status 为 live | 待执行 |
| P1 | 开始累计 effective_stable_days | 待执行 |

---

## 10. 相关文档

- `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md` - 正式主链定义
- `docs/LEGACY_OPENCLAW_DEPENDENCY_STATUS.md` - OpenClaw legacy 状态
- `artifacts/verification/EGOCORE_EMOTIOND_DIRECT_VERIFICATION.md` - 直连验证报告
