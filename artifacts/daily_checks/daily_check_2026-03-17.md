# OpenEmotion 每日检查报告

**日期**: 2026-03-17
**时间**: 2026-03-17T08:00:13-05:00

---

## 1. 服务状态

```bash
● emotiond.service - OpenEmotion Daemon (emotiond)
     Loaded: loaded (/home/moonlight/.config/systemd/user/emotiond.service; enabled; preset: enabled)
     Active: active (running) since Tue 2026-03-17 07:04:07 CDT; 56min ago
   Main PID: 1830491 (python)
      Tasks: 1 (limit: 14351)
     Memory: 40.3M (peak: 42.0M)
        CPU: 36.018s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/emotiond.service
             └─1830491 python -m emotiond.main --port 18080

```

**状态**: ✅ 运行中

---

## 2. API 功能验证

### /health
```json
{"ok":true,"ts":"2026-03-17T08:00:13.548344","emotiond":{"version":"0.1.0","status":"running","core_enabled":true}}
```
**状态**: ✅ 正常

### /decision
```json
{"status":"ok","decision_id":10,"action":"repair_offer","explanation":{"emotion":{"top2":[["loneliness",0.005285309553146362]],"all":{"anger":0.0,"sadness":0.0,"anxiety":0.0,"joy":0.0,"loneliness":0.005285309553146362}},"interoception":{"social_safety":0.6,"energy":1.0},"relationships":{"bond":2.0483656576768106e-44,"grudge":0.0,"trust":0.5000000000000003,"repair_bank":0.0},"candidates":[{"action":"withdraw","score":0.10850000000000007,"predicted_delta":{"safety":0.01,"energy":0.02},"reasons":["Energy-preserving (+0.02)"]},{"action":"repair_offer","score":0.10750000000000007,"predicted_delta":{"safety":0.05,"energy":-0.04},"reasons":["Predicted to improve safety (+0.05)"]},{"action":"approach","score":0.10550000000000008,"predicted_delta":{"safety":0.03,"energy":-0.02},"reasons":["Predicted to improve safety (+0.03)","Safe to approach"]}],"selected":"repair_offer","selection_reasons":["Selected via stochastic process (score: 0.108)","Repair attempt may reduce grudge"],"persistence":{"strategy":"normal","reason":"normal_operation","trace":{"strategy":"normal","reason":"normal_operation","persistence_pressure":0.202,"risk":0.15,"ambiguity":0.0,"expected_info_gain":1.0,"tradeoff_score":0.1486,"dominant_drivers":[],"conservative_trigger":null,"repair_trigger":null,"retreat_trigger":null},"policy_override":null}},"target_id":"telegram:8420019401","created_at":"2026-03-17 10:55:36","correlation_id":null,"policy_version":"7.5.0","schema_version":"1.0"}
```
- correlation_id: ✅
- policy_version: ✅
- schema_version: ✅

---

## 3. drift_guard 检查

```
DRIFT_GUARD_OK
- workspace 下无 OpenEmotion 副本
- systemd service 指向真源
- 无旧路径引用

**状态**: ✅ 通过
```

---

## 4. 隔离区状态

**位置**: `/home/moonlight/Project/Quarantine/openemotion_workspace_20260315`
**大小**: 70M
**状态**: 🟡 存在（待删除）
**距封板**: 2 天

---

## 5. 综合评估

**整体状态**: ✅ 正常
**发现问题**: 0

---

**报告生成**: 2026-03-17T08:00:13-05:00
