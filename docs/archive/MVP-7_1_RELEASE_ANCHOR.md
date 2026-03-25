# MVP-7.1 Release Anchor

**Release Version:** 7.1.0  
**Release Date:** 2026-03-02  
**Status:** COMPLETE ✅

## Release Commit

```
commit: 5d4de35
message: chore(mvp71): complete MVP-7.1 - quarantine cleared, all hard gates pass
branch: feature-emotiond-mvp
```

## Tool Policy Version

```
tool_policy_version: 1.0.0
source: emotiond/tool_policy.py::ToolPolicy.POLICY_VERSION
hash: Generated from registry state + policy version
generation_logic: SHA256(policy_version + registry_hash)[:16]
```

## Hard Gates Verification

| Gate | Status | Evidence |
|------|--------|----------|
| B1 | ✅ PASS | 0 failed tests, 0 skipped (quarantine empty) |
| B2 | ✅ PASS | All decisions include tool_policy_version + trace_id |
| B3 | ✅ PASS | holdout/ood stable, no regression |
| B4 | ✅ PASS | intervention/ablation causal tests pass |

### B1 Verification Command

```bash
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
source .venv/bin/activate
python -m pytest tests/ -q --tb=no
# Result: 2094 collected, 0 failed
```

### B2 Verification

- `emotiond/tool_policy.py`: PolicyDecision includes policy_version
- `emotiond/tool_registry.py`: Registry includes version_hash
- `emotiond/agent_router.py`: ExecutionPlan includes policy_version

### B3 Verification

- holdout_set: Stable (no regression)
- ood_set: Stable (no regression)
- quarantine.yml: 0 tests remaining

### B4 Verification

```bash
python -m pytest tests/test_tool_system.py -v --tb=short
# Result: 36 passed, 0 failed
# - intervention_effect_size: Verified
# - ablation_drop_ratio: Verified
```

## Key Evidence Paths

```
Core Modules:
- emotiond/tool_registry.py      # Tool definitions, permissions, cost models
- emotiond/tool_policy.py        # Policy engine, reason codes, audit
- emotiond/agent_router.py       # Intent classification, routing, fallback
- emotiond/dmn_tick.py           # Background tick, tool-needed backlog
- emotiond/offline_rollouts.py   # Rollout simulation

Test Files:
- tests/test_tool_system.py      # 36 tests for tool system
- tests/quarantine.yml           # 0 tests in quarantine

Scenarios:
- scenarios/test_tool_availability_intervention.yaml
- scenarios/test_tool_availability_ablation.yaml

Documentation:
- docs/MVP-7.0-self-model.md
- docs/SCENARIOS-self-awareness.md
```

## Deliverables Summary

| US | Description | Status |
|----|-------------|--------|
| US-7101 | ToolRegistry v0 + ToolPolicy v0 | ✅ |
| US-7102 | Capability Router | ✅ |
| US-7103 | Audit & Provenance | ✅ |
| US-7104 | Causal Tests (intervention/ablation) | ✅ |
| US-7105 | DMN Integration | ✅ |

## Architecture Principle

**External Symbolic Constraint (B-route)**

- LLM does NOT decide tool permissions
- LLM only proposes candidate plans
- ToolPolicy decides and logs to audit

This ensures:
1. Deterministic permission decisions
2. Traceable reason codes
3. No prompt-injection bypass
4. Aggregatable statistics

## Tag

```bash
# Local annotated tag (not pushed)
git tag -a mvp-7.1.0 -m "MVP-7.1 Release: Tool Registry + Policy + Router"
```

## Next Milestone

MVP-7.2: Tool Execution Safety Shell + Agency Loop

---

*Generated: 2026-03-02 09:55 CST*
