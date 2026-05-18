# MVP-7.0 Release Anchor

**Status:** Release Candidate (unpublished)
**Anchor Commit:** `d41ae32`
**Latest Commit:** `4516fc7`
**Branch:** `feature-emotiond-mvp`
**Date:** 2026-03-02

## Core Capabilities

### Milestone A: 防跑偏底盘 (US-641~644)
- **KnobRegistry** - 可更新参数白名单 + hard_freeze 保护
- **Frozen Holdout + OOD Harness** - 防过拟合结构
- **Provenance + Signature Attribution** - 自他边界不可伪造 (HMAC)
- **追溯拆分** - threshold_config_hash + candidate_param_hash

### Milestone B: 因果证据层 (US-651~653)
- **Homeostasis Drive v0** - drive_error + emotion_from_drive
- **Intervention Test** - 同事件流不同内状态 → 行为显著不同
- **Ablation Test** - 关掉机制差异必须消失

### Milestone C: 主体建模层 (US-701~707)
- **Self-Model v0** - Identity/Capability/Ownership constraints
- **Episodic Memory v0** - episode 写入/检索/TTL
- **Self-Other Boundary v0** - 边界强约束
- **Offline Rollouts v0** - 默认关闭，仅诊断
- **Meta-Cognitive Override** - Prompt vs BodyState 冲突检测
- **Mirror Test** - 身份与自我归因
- **DMN Tick v0** - 后台连续性 + 账本审计 + 门控主动性

## Verification Evidence

### Test Suite
```
pytest tests/ -q
Result: 2028 passed, 10 skipped, 0 failed
```

### Key Reports
- Audit Summary: `docs/B1_B4_AUDIT_SUMMARY.md`
- Threshold Config: `scripts/eval_thresholds_v2_3.json`
- Scenario Sets: `scenarios/*.yaml`

### Gate Verification
| Gate | Status | Evidence |
|------|--------|----------|
| B1 回归不破坏 | ✅ PASS | 2028/2039 tests passed |
| B2 追溯完整 | ✅ PASS | threshold_config_hash + code_version present |
| B3 防过拟合 | ✅ PASS | holdout/ood sets defined |
| B4 因果证据 | ✅ PASS | intervention/ablation tests passing |

## Local Tag
```bash
git tag -a mvp-7.0.0 d41ae32 -m "MVP-7.0 Release Anchor"
```

## Key Files
| Category | Path |
|----------|------|
| Core Modules | `core/self_model.py`, `core/episodic_memory.py`, `core/dmn_tick.py` |
| Drive System | `core/drive_homeostasis.py` |
| Provenance | `core/provenance.py` |
| Tests | `tests/test_phase3_modules.py`, `tests/test_causal_evidence.py` |
| Scenarios | `scenarios/test_intervention_*.yaml`, `scenarios/test_ablation_*.yaml` |

## Release Notes (Draft)

### New Features
1. **Self-Model System** - 独立主体模块参与决策
2. **Homeostasis Drives** - 动机与稳态压力影响策略
3. **Episodic Memory** - 跨时间连续性记忆系统
4. **DMN Tick** - 低频后台巩固与主动提醒门控
5. **HMAC Provenance** - 防注入的自他边界签名

### Breaking Changes
- None (backward compatible with MVP-6.x)

### Known Limitations
- 10 skipped tests (quarantine pending)
- 253 warnings (baseline pending)
- OOD generation non-deterministic (seed pending)

---

*This document serves as the release anchor for MVP-7.0. Tag push and GitHub Release require explicit approval.*
