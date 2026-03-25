# OpenEmotion 每日检查报告

**日期**: 2026-03-16
**时间**: 2026-03-16T08:00:13-05:00

---

## 1. 服务状态

```bash
○ emotiond.service - OpenEmotion emotiond daemon (canonical)
     Loaded: loaded (/home/moonlight/.config/systemd/user/emotiond.service; disabled; preset: enabled)
     Active: inactive (dead)

Mar 15 06:05:22 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     127.0.0.1:57076 - "GET /health HTTP/1.1" 200 OK
Mar 15 06:05:22 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     127.0.0.1:57078 - "GET /decision HTTP/1.1" 200 OK
Mar 15 06:05:22 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     127.0.0.1:57088 - "GET /health HTTP/1.1" 200 OK
Mar 15 08:00:02 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     127.0.0.1:43312 - "GET /health HTTP/1.1" 200 OK
Mar 15 08:00:02 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     127.0.0.1:43326 - "GET /decision HTTP/1.1" 200 OK
Mar 16 07:47:39 moonlight-VMware-Virtual-Platform uvicorn[785162]: INFO:     Shutting down
```

**状态**: ❌ 未运行

---

## 2. API 功能验证

### /health
```json
{"error": "无法连接"}
```
**状态**: ❌ 异常

### /decision
```json
{"error": "无法连接"}
```
- correlation_id: ❌ 缺失
- policy_version: ❌ 缺失
- schema_version: ❌ 缺失

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
**距封板**: 1 天

---

## 5. 综合评估

**整体状态**: ⚠️ 有问题
**发现问题**: 2

---

**报告生成**: 2026-03-16T08:00:13-05:00
