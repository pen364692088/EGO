# P7 FAILURE_SAMPLES

## 环境阻塞

### `pytest` 不可用

- command: `python3 -m pytest --version`
- result: `/usr/bin/python3: No module named pytest`
- impact: 无法在当前环境执行 P7 守护测试与回归矩阵

## 兼容输入仍需保留的样本

### legacy `risk` alias

- location:
  - `EgoCore/tests/test_proto_self_contracts.py`
  - `OpenEmotion/openemotion/proto_self/tests/test_schema_contract.py`
- reason:
  - 这些测试用于证明 schema/adapter 仍能吸收历史输入
- status:
  - compatibility-only，不是正式 producer 合约

### numeric `risk_level`

- location:
  - `OpenEmotion/openemotion/proto_self/tests/test_kernel_replay.py`
  - `OpenEmotion/openemotion/proto_self/tests/test_kernel_identity.py`
  - `OpenEmotion/openemotion/proto_self/tests/test_kernel_drive_field.py`
  - `OpenEmotion/openemotion/proto_self/tests/test_kernel_boundaries.py`
- reason:
  - 这些测试依赖 schema 层把 numeric input 归一为 canonical string 或再映射到内部 caution/risk bias
- status:
  - compatibility-only，当前不能据此反推 producer 仍可输出数值

## 非本任务冲突但容易误判的样本

### OpenEmotion 其他领域里的数值 `risk`

- locations:
  - `OpenEmotion/tests/mvp10/*`
  - `OpenEmotion/tests/mvp11/*`
  - `OpenEmotion/tests/test_rollout_v0.py`
- reason:
  - 这些 `risk` 多为 EFE / 候选动作 / 资源代价 / rollout 指标，不是 host runtime `safety_context.risk_level`
- status:
  - out-of-scope for P7 canonical host risk authority
