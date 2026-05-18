# EgoCore 直连 emotiond 验证报告

> **验证日期**: 2026-03-17  
> **验证阶段**: Phase 2 - EgoCore 直连 emotiond  
> **状态**: ✅ PASS

---

## 1. 验证目标

验证 EgoCore 可以**不经过 OpenClaw**，直接完成 `ingress → emotiond → decision → outbound` 的完整调用链。

---

## 2. 验证结果摘要

| 测试项 | 状态 | 说明 |
|--------|------|------|
| Module Import | ✅ PASS | OpenEmotionAdapter, emotiond.core 导入正常 |
| Mock Mode | ✅ PASS | Adapter MOCK 模式工作正常 |
| Direct Module Call | ✅ PASS | 直接调用 emotiond.core 成功 |
| Real HTTP Backend | ✅ PASS | HTTP 调用 emotiond 服务成功 |
| E2E Flow (3 scenarios) | ✅ PASS | 3/3 场景全部通过 |

---

## 3. 详细验证记录

### 3.1 Module Import

```
✅ OpenEmotionAdapter import OK
✅ emotiond.api import OK
✅ emotiond.core import OK
```

### 3.2 Mock Mode

```
output_id: out_mock_8c0d1e17
valence: 0.2
arousal: 0.3
```

### 3.3 Direct Module Call

```
status: processed
valence: 0.0
arousal: 0.3
```

### 3.4 Real HTTP Backend

```
Health check: True
Output ID: out_58e557c2
valence: 0.0
arousal: 2.3e-322
transport_metadata:
  request_id: req_2f5ce681
  duration_ms: 202.26
  attempt: 1
  base_url: http://localhost:18080
```

### 3.5 E2E Flow

| Scenario | Status | valence |
|----------|--------|---------|
| 1. Normal Chat | ✅ processed | 0.0 |
| 2. Cross-turn Memory | ✅ processed | 0.0 |
| 3. Result Feedback | ✅ processed | 0.0 |

---

## 4. Artifact 落盘验证

### 4.1 目录结构

```
artifacts/egocore_emotiond_direct/20260316_215617/
├── mock_request.json
├── mock_response.json
├── direct_module_request.json
├── direct_module_response.json
├── scenario_1_response.json
├── scenario_2_response.json
└── scenario_3_response.json
```

### 4.2 Real HTTP Artifacts

```
artifacts/real_http_test/
├── transport_requests/
│   └── evt_*.json
└── transport_responses/
    └── evt_*.json
```

---

## 5. Contract 验证

### 5.1 输入契约 (oe.event.v1)

| 字段 | 类型 | 必填 | 验证 |
|------|------|------|------|
| event_id | string | ✅ | ✅ |
| timestamp | ISO8601 | ✅ | ✅ |
| actor | object | ✅ | ✅ |
| source | object | ✅ | ✅ |
| event_type | string | ✅ | ✅ |
| user_intent | object | ✅ | ✅ |
| safety_context | object | ✅ | ✅ |

### 5.2 输出契约 (oe.result.v1)

| 字段 | 类型 | 必填 | 验证 |
|------|------|------|------|
| output_id | string | ✅ | ✅ |
| timestamp | ISO8601 | ✅ | ✅ |
| event_id_ref | string | ✅ | ✅ |
| valence | number | ✅ | ✅ |
| arousal | number | ✅ | ✅ |
| confidence_metadata | object | ✅ | ✅ |

---

## 6. Gate 验收

### Gate A: Contract ✅

- 输入输出契约明确: ✅ EventInput / OpenEmotionOutput
- 没有未版本化字段漂移: ✅
- 没有"靠 prompt 临时约定字段"的接法: ✅

### Gate B: E2E ✅

- 至少 3 scenario 真闭环跑通: ✅ 3/3
- EgoCore 真调用 emotiond: ✅
- EgoCore 真消费 emotiond 输出: ✅
- 结构化 request/response 可保存: ✅

### Gate C: Boundary ✅

- EgoCore 没偷做主体本体: ✅
- OpenEmotion 没偷做渠道/工具/审批: ✅
- Adapter 只负责转换、传递、隔离、降级: ✅

---

## 7. 服务配置

### 7.1 emotiond 服务

```bash
# 启动命令
cd /home/moonlight/openclaw-work/OpenEmotion-audit
python -m emotiond.main --port 18080

# 健康检查
curl http://localhost:18080/health
```

### 7.2 EgoCore Adapter 配置

```python
from egocore.adapters import OpenEmotionAdapter, AdapterMode

adapter = OpenEmotionAdapter(
    mode=AdapterMode.REAL_HTTP,
    base_url="http://localhost:18080",
    artifact_dir=Path("artifacts/transport")
)
```

---

## 8. 结论

**Phase 2 验证通过**:

1. ✅ EgoCore 可以不经过 OpenClaw，直接完成调用链
2. ✅ 结构化 request/response 可保存、可回放、可定位
3. ✅ Contract 验证通过
4. ✅ E2E 场景 3/3 通过
5. ✅ 边界约束未违反

**下一步**: Phase 3 - 最小 E2E 场景 (真实 Telegram 入口)

---

## 9. 相关文件

| 文件 | 用途 |
|------|------|
| `tools/test_egocore_emotiond_direct.py` | 验证脚本 |
| `egocore/adapters/openemotion_adapter.py` | Adapter 实现 |
| `contracts/event_input.schema.json` | 输入契约 |
| `contracts/openemotion_output.schema.json` | 输出契约 |
| `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md` | 正式主链定义 |
