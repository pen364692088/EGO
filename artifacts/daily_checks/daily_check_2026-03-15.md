# OpenEmotion 每日检查报告

**日期**: 2026-03-15
**时间**: 2026-03-15T06:05:22-05:00

---

## 1. 服务状态

```bash
● emotiond.service - OpenEmotion emotiond daemon (canonical)
     Loaded: loaded (/home/moonlight/.config/systemd/user/emotiond.service; disabled; preset: enabled)
     Active: active (running) since Sun 2026-03-15 05:41:40 CDT; 23min ago
   Main PID: 785162 (uvicorn)
      Tasks: 1 (limit: 14351)
     Memory: 41.5M (peak: 43.1M)
        CPU: 17.066s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/emotiond.service
             └─785162 /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/.venv/bin/python3 /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/.venv/bin/uvicorn emotiond.api:app --host 127.0.0.1 --port 18080

```

**状态**: ✅ 运行中

---

## 2. API 功能验证

### /health
```json
{"ok":true,"ts":"2026-03-15T06:05:22.312118","emotiond":{"version":"0.1.0","status":"running","core_enabled":true}}
```
**状态**: ✅ 正常

### /decision
```json
{"status":"no_decision","decision":null,"correlation_id":null,"policy_version":"7.5.0","schema_version":"1.0"}
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
**距封板**: 0 天

---

## 5. 综合评估

**整体状态**: ✅ 正常
**发现问题**: 0

---

**报告生成**: 2026-03-15T06:05:22-05:00
