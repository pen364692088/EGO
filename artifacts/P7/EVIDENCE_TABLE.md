# P7 EVIDENCE_TABLE

| claim | evidence | result |
|---|---|---|
| P7 开始前正式主链存在多个 message risk authority source | `runtime_v2/proto_self_runtime.py`、`context_assembler.py`、`semantic_router.py`、`approval_policy.py` 各自维护风险规则 | 成立 |
| canonical risk source 已收口到 `EgoCore/app/risk_signal.py` | 新增 `app/risk_signal.py`，定义 canonical levels、rule set、normalizer | 成立 |
| `runtime_v2` 已不再自己维护 risk 词表 | `proto_self_runtime.py` 只调用 `assess_message_risk_level()` / `risk_level_from_external_result()` | 成立 |
| `context_assembler` 已改为消费 canonical scorer | `context_assembler.py` 只调用 `assess_message_risk_level()` | 成立 |
| `semantic_router` 已改为消费 canonical scorer | `semantic_router.py` 只调用 `is_high_risk_message()` | 成立 |
| `approval_policy` 不再保留第二套 message risk 词表 | `approval_policy.py` 已删本地 `HIGH_RISK_PATTERNS`，`is_high_risk_operation()` 只调 canonical scorer | 成立 |
| formal producer 已只输出 canonical `risk_level` string | `proto_self_runtime.py`、`event_builder.py` 均只写 `risk_level` | 成立 |
| `legacy risk` 与 numeric `risk_level` 已降为 compat-only 输入 | `app/risk_signal.py` 与 `OpenEmotion/openemotion/proto_self/schemas.py` 负责吸收兼容输入 | 成立 |
| host->proto-self 边界会删除 legacy `risk` 字段 | `normalize_safety_context()` 中 `pop("risk", None)`；`test_proto_self_contracts.py` / `test_schema_contract.py` 验证吸收行为 | 成立 |
| 守护测试已覆盖 canonical scorer 和 compat normalization | `EgoCore/tests/test_risk_signal_authority.py`、`OpenEmotion/openemotion/proto_self/tests/test_schema_contract.py` | 成立 |
| 旧脚本样本不再示范 legacy `risk` 为正式字段 | `p0_r2_e2e_test.py`、`p0_r3_e2e_test.py` 仅使用 `risk_level` | 成立 |
| EgoCore 正式 app/scripts/tests 中已无旧 message risk 词表副本 | `rg -n '_HIGH_RISK_KEYWORDS|_MEDIUM_RISK_KEYWORDS|high_risk_keywords|medium_risk_keywords|HIGH_RISK_PATTERNS = \\[' EgoCore/app EgoCore/scripts EgoCore/tests -S` 返回空 | 成立 |
| 本次修改文件语法有效 | `python3 -m py_compile ...` 通过 | 成立 |
| 当前环境无法做 pytest 回归 | `python3 -m pytest --version` 返回 `No module named pytest` | 阻塞 |

## 关键命令摘录

| command | output summary |
|---|---|
| `rg -n 'from app\\.risk_signal import|assess_message_risk_level|normalize_safety_context\\(|is_high_risk_message\\(' EgoCore/app EgoCore/scripts EgoCore/tests -S` | 显示 runtime、scripts、tests 已指向 canonical source |
| `rg -n '_HIGH_RISK_KEYWORDS|_MEDIUM_RISK_KEYWORDS|high_risk_keywords|medium_risk_keywords|HIGH_RISK_PATTERNS = \\[' EgoCore/app EgoCore/scripts EgoCore/tests -S` | 无命中，证明旧规则副本已清空 |
| `python3 -m py_compile ...` | PASS |
| `python3 -m pytest --version` | BLOCKED: `No module named pytest` |
