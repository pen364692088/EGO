# 模块 Gate 检查清单

> 复制此文件，重命名为 `{module_name}_gate_checklist.md`，逐项勾选

---

## 模块信息

| 字段 | 值 |
|------|-----|
| 模块名称 | |
| 版本 | |
| 检查日期 | |
| 检查人 | |

---

## Gate A｜Contract 检查

### A.1 Schema 定义

- [ ] input schema 已定义且文档化
- [ ] output schema 已定义且文档化
- [ ] error schema 已定义且文档化
- [ ] fallback schema 已定义且文档化
- [ ] timeout schema 已定义且文档化

### A.2 字段验证

- [ ] 所有必填字段已标注
- [ ] 字段类型已明确
- [ ] 字段约束已定义（长度、范围、格式等）
- [ ] 示例数据已提供

### A.3 错误定义

- [ ] 错误码列表已完整
- [ ] 每个错误码有明确说明
- [ ] 错误严重级别已标注
- [ ] 用户可见性已明确

### A.4 契约冻结

- [ ] contract 已评审
- [ ] contract 已冻结（状态 = frozen）
- [ ] 变更流程已定义

**Gate A 结论**: ☐ 通过 ☐ 不通过 ☐ 有条件通过

**证据**:
- Contract 文件: `link/to/contract.yaml`
- 评审记录: `link/to/review.md`

---

## Gate B｜E2E 检查

### B.1 Success 场景

- [ ] 正常输入返回预期输出
- [ ] 输出格式符合 schema
- [ ] metrics 正确记录
- [ ] logs 正确输出

### B.2 Skip 场景

- [ ] 无效输入优雅跳过
- [ ] skip 原因记录到 log
- [ ] metrics 正确记录 skip

### B.3 Fallback 场景

- [ ] 依赖异常触发 fallback
- [ ] fallback 返回默认值
- [ ] fallback 记录 warning log
- [ ] 用户无感知或适当提示

### B.4 Error 场景

- [ ] 错误返回符合 error schema
- [ ] 错误码正确
- [ ] error log 输出
- [ ] 不泄露敏感信息

### B.5 边界场景

- [ ] 空输入处理
- [ ] 超大输入处理
- [ ] 特殊字符处理
- [ ] 并发请求处理

### B.6 测试覆盖

- [ ] unit tests 通过
- [ ] contract tests 通过
- [ ] integration tests 通过
- [ ] fallback tests 通过

**Gate B 结论**: ☐ 通过 ☐ 不通过 ☐ 有条件通过

**证据**:
- 测试报告: `link/to/test_report.md`
- 覆盖率: XX%

---

## Gate C｜Preflight 检查

### C.1 主链安全

- [ ] 不会破坏当前稳定主链
- [ ] 不修改主链核心逻辑
- [ ] 不引入新的阻塞点
- [ ] 不增加主链耦合度

### C.2 集成点

- [ ] integration point 已明确
- [ ] integration point 唯一
- [ ] integration point 可控
- [ ] 接入方式已文档化

### C.3 可控性

- [ ] feature flag 已定义
- [ ] 支持运行时开关
- [ ] 支持快速 disable
- [ ] 开关默认值 = off

### C.4 可回滚

- [ ] 回滚方案已定义
- [ ] 回滚时间 < 5 分钟
- [ ] 回滚无需重启（或已接受）
- [ ] 回滚验证方法已定义

### C.5 可观测

- [ ] metrics 已埋点
- [ ] logs 已埋点
- [ ] 关键路径有 trace
- [ ] dashboard 已配置（或已计划）

### C.6 依赖就绪

- [ ] 所有必需依赖已就绪
- [ ] 依赖有 fallback 方案
- [ ] 依赖故障不影响主链

### C.7 文档完整

- [ ] contract 文档完整
- [ ] design note 完整
- [ ] fallback note 完整
- [ ] integration plan 完整

**Gate C 结论**: ☐ 通过 ☐ 不通过 ☐ 有条件通过

**证据**:
- 集成计划: `link/to/integration_plan.md`
- 回滚方案: `link/to/rollback_plan.md`

---

## 综合评估

### Gate 汇总

| Gate | 状态 | 检查日期 | 检查人 |
|------|------|----------|--------|
| A - Contract | ☐ 通过 ☐ 不通过 | | |
| B - E2E | ☐ 通过 ☐ 不通过 | | |
| C - Preflight | ☐ 通过 ☐ 不通过 | | |

### 阻塞项

<!-- 如果有未通过的项，列出阻塞原因 -->

### 风险说明

<!-- 即使通过，也要说明已知风险 -->

### 接主链建议

☐ 可以接入
☐ 有条件接入（需满足 XXX）
☐ 暂不建议接入

---

## 签字

| 角色 | 姓名 | 日期 | 意见 |
|------|------|------|------|
| 模块负责人 | | | |
| 技术评审 | | | |
| 最终批准 | | | |

---

## 附录：快速检查命令

```bash
# 运行 preflight 检查
python tools/module_preflight_check.py --module {module_name}

# 运行所有测试
pytest modules/{module_name}/tests/ -v

# 检查 contract 有效性
python tools/validate_contract.py modules/{module_name}/contract.yaml
```
