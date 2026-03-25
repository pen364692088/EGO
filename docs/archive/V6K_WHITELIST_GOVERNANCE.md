# V6K: Whitelist Governance + Periodic Receipts

> Status: Implemented
> Date: 2026-03-16
> Capability Owner: OpenEmotion

## Overview

v6k implements unified governance for the production whitelist:

1. **Whitelist Governance Evaluator** - Evaluates all scenarios with unified verdicts
2. **Periodic Receipt Generator** - Automatic daily/round/manual receipts
3. **Alert Manager** - Structured alerts for stability issues

## Problem Statement

v6a-v6j answered:
> Can individual scenarios be validated, promoted, and protected?

v6k answers:
> How do we govern the entire whitelist as a living system?

## Solution

### Whitelist Governance Evaluator

`emotiond/memory/embedding/whitelist_governance.py`

Evaluates governance at two levels:

#### Scenario-Level Verdicts
- `healthy` - All metrics within thresholds
- `observe` - Minor issues or insufficient data
- `demote_candidate` - Significant stability issues
- `rollback_candidate` - Critical issues (wrong_user_guard)

#### Whitelist-Level Verdicts
- `stable` - All scenarios healthy
- `observe` - Some scenarios need attention
- `expansion_blocked` - Critical issues prevent expansion
- `expansion_ready_candidate` - All scenarios stable, ready for new scenarios

### Periodic Receipt Generator

`emotiond/memory/embedding/periodic_receipts.py`

Generates structured receipts:
- **Daily receipt** - End-of-day summary
- **Round-based receipt** - After observation rounds
- **Manual receipt** - Ad-hoc governance checks

### Alert Manager

`emotiond/memory/embedding/whitelist_alerts.py`

Detects and tracks:
- Provider health drops
- Latency regressions
- Fallback spikes
- Wrong user guard triggers
- Quality signal regressions

## Thresholds

### Scenario Healthy
- `wrong_user_guard_trigger_count = 0`
- `fallback_rate <= 5%`
- `provider_health_rate >= 98%`
- `p95_latency_ms <= 100`
- `quality_gain_signal > 0`

### Scenario Demote Candidate
- `fallback_rate > 10%`
- `provider_health_rate < 95%`

### Scenario Rollback Candidate
- `wrong_user_guard_trigger_count > 0`

### Whitelist Expansion Ready
- All scenarios healthy
- No rollback candidates
- No critical blockers

## Usage

### Generate Receipt

```bash
# Daily receipt
python scripts/generate_whitelist_receipt.py --mode daily

# Round-based receipt
python scripts/generate_whitelist_receipt.py --mode round --round-id 1

# Manual receipt
python scripts/generate_whitelist_receipt.py --mode manual --reason "Ad-hoc check"
```

### Evaluate Governance

```python
from emotiond.memory.embedding.whitelist_governance import (
    WhitelistGovernanceEvaluator,
    WhitelistVerdict,
)

governance = WhitelistGovernanceEvaluator(registry)
summary = governance.evaluate_whitelist()

if summary.whitelist_verdict == WhitelistVerdict.STABLE:
    print("Whitelist is stable!")
```

## Current Whitelist State

| Scenario | Status | Verdict |
|----------|--------|---------|
| memory_search_hard_query | Promoted | Observe (no data) |
| narrative_recall_ambiguous_query | Promoted | Observe (no data) |
| long_context_semantic_lookup | Promoted | Observe (no data) |
| complex_semantic_reasoning | Promoted | Observe (v6j drill data) |

**Whitelist Verdict:** OBSERVE
**Expansion Readiness:** NOT_READY

## Artifacts

- `artifacts/eval/v6k/whitelist_governance_summary.json`
- `artifacts/eval/v6k/whitelist_receipt_daily_*.json`
- `artifacts/eval/v6k/whitelist_receipt_round_*.json`
- `artifacts/eval/v6k/whitelist_alert_summary.json`

## Tests

```bash
pytest tests/embedding/test_whitelist_governance.py
```

## Relation to v6a-v6j

| Version | Capability |
|---------|------------|
| v6a-v6g | Individual scenario validation and pilot |
| v6h | Production whitelist promotion |
| v6i | Post-promotion stability |
| v6j | Guard drill completion |
| **v6k** | **Whitelist governance + periodic receipts** |

## Key Invariants

1. **Unified Truth** - Single source of governance truth
2. **Periodic Receipts** - Automatic, structured audit trail
3. **Scenario Isolation** - Each scenario evaluated independently
4. **Whitelist Aggregate** - Overall whitelist health calculated
5. **Expansion Gates** - Clear criteria for adding new scenarios
