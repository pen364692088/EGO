# Observation Sample Index

## 窗口定义

- 观察窗口起点：`2026-03-26`
- 样本来源约束：`artifacts/telegram_real_mainline_v1/real_telegram/`
- 只承认真实 Telegram 主链样本

## 样本规模

| 指标 | 数值 |
|---|---|
| 窗口样本总数 | `58` |
| 完整 evidence bundle | `35` |
| 缺项 / 不完整 | `23` |
| 覆盖日期 | `2026-03-26`、`2026-03-27` |

## 核心代表样本

### 1. chat / reply

- `sample_20260326_234312_3ff295bb`
  - 输入：`你好啊`
  - 结果：`ingress:user_request / unknown`
  - 用途：一般聊天路径，观察一般 ingress family
- `sample_20260327_074228_a8d1a279`
  - 输入：`你能做定时任务吗`
  - 结果：跨日一般 ingress 延续

### 2. execute_task / tool 成功

- `sample_20260326_230231_74277be4`
  - 输入：`如果刚才失败了，现在读取 ... CLAUDE.md 前 1 行`
  - 结果：`tool:file / success`
- `sample_20260326_232738_49b65b2e`
  - 输入：`再读取一次 ... CLAUDE.md 前 1 行`
  - 结果：重复 success，验证不重复误点 repair

### 3. execute_task / tool blocked / failure

- `sample_20260326_232655_3f3f89cb`
  - 输入：`读取 ... missing_closure_probe.md 前 1 行`
  - 结果：`tool:file / blocked`
- `sample_20260326_234618_b4b7792b`
  - 输入：搜索论文请求
  - 结果：`tool:shell / blocked`

### 4. failure -> repair -> success

- `sample_20260326_232655_3f3f89cb`
  - blocked，`mode=repair`
- `sample_20260326_232715_271e229b`
  - retry-success，`repair_closure=true`
- `sample_20260326_232738_49b65b2e`
  - repeated success，`repair_closure=false`

### 5. 重复相似任务

- `sample_20260326_234312_3ff295bb`
- `sample_20260326_234332_e76560e7`
- `sample_20260326_234426_aac8b8e6`
- `sample_20260326_234708_4c4c5e92`
- `sample_20260326_234834_9c7df1d6`
- `sample_20260327_074212_35c4cb68`
- `sample_20260327_074228_a8d1a279`

这些样本都落在同一类一般 ingress family 上，可用于观察 cycle 重入与跨日延续。

## 缺失类别

以下任务单要求的类别，本轮没有拿到直接真实样本：

- `/new`
- `restart`
- `state restore` 的直接触发样本

当前只能由状态文件间接支持 continuity，不能视作该类别已覆盖。

## 关键观察点

### A. P4 修复后的真实链

- `sample_20260326_232655_3f3f89cb`
- `sample_20260326_232715_271e229b`
- `sample_20260326_232738_49b65b2e`

这组三连样本是本轮最关键的 repair/family 证据。

### B. 跨日延续

- `sample_20260326_234312_3ff295bb`
- `sample_20260326_234332_e76560e7`
- `sample_20260326_234426_aac8b8e6`
- `sample_20260326_234708_4c4c5e92`
- `sample_20260326_234834_9c7df1d6`
- `sample_20260327_074212_35c4cb68`
- `sample_20260327_074228_a8d1a279`

这些样本共同证明一般 ingress family 跨日连续存在。

## 参考但不计为完整成功样本

以下样本位于窗口内，但 evidence 不完整，应进入 failure/gap ledger，而不是成功计数：

- `sample_20260326_122012_a1eb9987`
- `sample_20260326_130620_fa6a1303`
- `sample_20260326_134949_b14ecef8`
- `sample_20260326_135004_de5a2b74`
- `sample_20260326_140841_7fd57d3e`
- `sample_20260326_141603_c295f138`
- `sample_20260326_141641_68a5a243`
- `sample_20260326_142359_945ae501`
- `sample_20260326_143224_1406bcb4`
- `sample_20260326_143303_9df6b133`
- `sample_20260326_143624_eb57644d`
- `sample_20260326_143641_05b02d55`
- `sample_20260326_143708_8a6c95fe`
- `sample_20260326_154600_e34d5fbc`
- `sample_20260326_154804_12ed4c28`
- `sample_20260326_180956_097602f5`
- `sample_20260326_181045_4e639441`
- `sample_20260326_181325_7177ff8e`
- `sample_20260326_184809_ab5a513f`
- `sample_20260326_204952_a1ad48c9`
- `sample_20260326_222703_9e2bb07b`
- `sample_20260326_223755_238449d4`
- `sample_20260326_223842_b8d9e1f2`
