# Numeric Leak Source Trace Report

**Task ID**: MVP11_5_T03
**Generated**: 2026-03-08T17:45:00-05:00

---

## Executive Summary

**Primary Finding**: Numeric leaks are being **detected but not blocked** because the system is in **Phase B shadow mode**.

| Metric | Value |
|--------|-------|
| Total Numeric Leaks Detected | 802 |
| Leaks in Interpreted Mode | 768 (95.8%) |
| Leaks Blocked | 0 (shadow mode) |
| Would Block if Enforced | 802 (100%) |

---

## Source Modules Identified

### MOD-001: self_report_validator.py
**Role**: Violation Detection

- 检测 LLM 输出中的 numeric leak 模式
- 定义 NUMERIC_PATTERNS 匹配规则
- **Status**: ✅ Working as intended

### MOD-002: numeric_leak_filter.py
**Role**: Numeric Filtering

- `sanitize()` - 清理输出
- `check_response()` - 检查并返回评估
- `should_block()` - 决定是否阻止
- **Status**: ✅ Working as intended

### MOD-003: self_report_consistency_checker.py
**Role**: Orchestration & Logging

- 整合 validator 和 filter 的检测结果
- 生成 `would_block` 标志
- 写入 shadow_log.jsonl
- **Status**: ⚠️ Working but not enforcing

**Critical Logic** (line 805):
```python
if not enforce_mode:
    return False  # Shadow mode: never block
```

### MOD-004: core.py
**Role**: LLM Orchestration

- 调用 consistency_checker 进行检测
- **Status**: ❓ Requires investigation

---

## Pipeline Gaps

### GAP-001: Shadow Mode No Enforcement (P0)

**Description**: 当前处于 Phase B shadow mode，violations 被检测但不阻止

**Evidence**:
```python
# self_report_consistency_checker.py:805
if not enforce_mode:
    return False  # Shadow mode: never block
```

**Impact**:
- 所有 802 个 detected violations 都进入了用户输出
- `would_block = true` 被记录，但没有实际阻止

---

### GAP-002: Interpreted Mode Vulnerability (P0)

**Description**: interpreted mode 允许 LLM 更多自由度，导致 95.8% 的 numeric leak

**Evidence**:
| Mode | Numeric Leaks | Percentage |
|------|--------------|------------|
| interpreted | 768 | 95.8% |
| numeric | 17 | 2.1% |
| style_only | 17 | 2.1% |

**Impact**: interpreted mode 是 numeric leak 的主要通道

---

### GAP-003: Output Stage Only Filtering (P1)

**Description**: numeric filter 在输出阶段检查，而非在 prompt 构建阶段阻止

**Impact**: LLM 仍然可以生成 numeric 内容，只是在输出时被检测

---

## Filter Bypass Paths

| Bypass ID | Name | Affected | Fix Required |
|-----------|------|----------|--------------|
| BYPASS-001 | shadow_mode_bypass | 802 | Switch to enforce mode |
| BYPASS-002 | interpreted_mode_generation | 768 | Prohibit numeric in prompt |
| BYPASS-003 | post_hoc_detection | all | Pre-generation constraint |

---

## Architecture Boundary Assessment

| Question | Answer |
|----------|--------|
| Requires architecture change? | ❌ No |
| Requires SRAP authority change? | ❌ No |
| Requires interpreted mode redefinition? | ✅ Yes |
| Requires raw_state injection change? | ❌ No |

**Conclusion**: interpreted mode 需要重新定义以禁止 numeric 生成，但不涉及 SRAP 权威链或 raw_state 注入策略的根本改变。

**Escalation Required**: ❌ No

---

## Minimum Fixes

### FIX-001: Enable Enforce Mode (P0)

**Description**: 切换到 Phase C enforce mode，使 `would_block` 生效

**Scope**: 配置变更
**Risk**: 低
**Impact**: 阻止 100% of detected numeric leaks

### FIX-002: Interpreted Mode Numeric Prohibition (P0)

**Description**: 在 interpreted mode 的 prompt 或约束中明确禁止 numeric 生成

**Scope**: `prompt_contracts/self_report.md` 或 `self_report_interpreter.py`
**Risk**: 中
**Impact**: 减少 interpreted mode 中的 numeric 生成

### FIX-003: Zero-Value Filter (P1)

**Description**: 添加 zero-value 特定过滤，阻止 `joy=0.0` 类型的输出

**Scope**: `numeric_leak_filter.py`
**Risk**: 低
**Impact**: 减少 40.7% of raw_state_direct_leak

---

## Affected Modules Summary

| Module | Role | Status | Action Required |
|--------|------|--------|-----------------|
| self_report_validator.py | Detection | ✅ OK | None |
| numeric_leak_filter.py | Filtering | ✅ OK | None |
| self_report_consistency_checker.py | Enforcement | ⚠️ Shadow | Enable enforce mode |
| core.py | Orchestration | ❓ Unknown | Investigate |

---

## Recommendations

### Immediate (P0)
1. **切换到 Phase C enforce mode** - 使 would_block 生效
2. **强化 interpreted mode numeric 禁止** - 在 prompt 层面阻止

### Follow-up (P1)
3. **添加 zero-value 特定过滤** - 减少 40.7% 的 leak
4. **调查 core.py 集成** - 确认 enforcement 调用点

---

## Next Recommended Task

**T03.1**: Enable Enforce Mode (config change)

这是一个最小修复任务，只需要配置变更，不涉及代码修改。

---

## Deliverable Status

- ✅ `artifacts/self_report/numeric_leak_source_trace.json`
- ✅ `artifacts/self_report/numeric_leak_source_trace.md`
- ✅ `source_modules`: 4 modules identified
- ✅ `pipeline_gaps`: 3 gaps documented
- ✅ `filter_bypass_paths`: 3 bypass paths mapped

---

**Generated**: 2026-03-08T17:45:00-05:00
