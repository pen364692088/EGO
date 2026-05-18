# v6k.2a: External Scheduler Integration + Alert-Governance Consistency Fix

## Summary

v6k.2a addresses two critical gaps identified in v6k.2:

1. **External Scheduler Evidence** - Added cron-based scheduling with evidence generation
2. **Alert → Governance Consistency** - Fixed severity reporting mismatch between alerts and governance consumption

## Changes

### A. External Scheduler Integration

#### Files Added
- `tools/whitelist_governance_daily.sh` - Daily cron script (3 AM UTC)
- `tools/whitelist_governance_round.sh` - Round-based cron script (every 6 hours)
- `ops/cron/whitelist_governance.cron` - Cron configuration

#### Evidence Generation
- `scheduler_evidence.json` - Generated on each run with:
  - `scheduler_type`: "cron"
  - `config_file`: Path to cron config
  - `trigger_time`: ISO timestamp
  - `trigger_type`: "daily" | "round"
  - `schedule`: Cron schedule string
  - `evidence_valid`: boolean

### B. Alert → Governance Consistency Fix

#### Problem Fixed
v6k.2 report showed:
- `quality_signal_regression = critical`
- But governance consumption said: "NO (only warning-level alerts)"

This inconsistency violated the rule: **critical alerts MUST update governance verdicts**.

#### Solution
1. Created `WhitelistOperationsReporter` class that:
   - Reads actual artifacts (not assumptions)
   - Groups alerts by second-level timestamp (fixes microsecond grouping issue)
   - Ensures critical alerts correctly trigger governance updates

2. Fixed `get_alerts_summary()` to group alerts by second-level timestamp, ensuring all alerts from the same batch are counted together.

#### Governance Impact Rules (Enforced)

| Rule | Condition | Impact |
|------|-----------|--------|
| 1 | critical alert exists | `whitelist_verdict_updated` = YES |
| 2 | critical alert exists | `expansion_readiness_updated` = YES |
| 3 | warning alert exists | `scenario_verdicts_updated` = YES |
| 4 | no alerts | governance stable |

## Verification

### Tests
- `tests/embedding/test_v6k2a_alert_governance_consistency.py` - 9 new tests
- All 24 tests pass (v6k2 + v6k2a)

### Consistency Checks
```
alerts_match_summary: PASS
summary_match_governance: PASS
critical_triggers_verdict_update: PASS
```

## Installation

To enable external scheduling:

```bash
# Add to crontab
crontab -e

# Add these lines:
0 3 * * * /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/whitelist_governance_daily.sh >> /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/logs/whitelist_governance.log 2>&1
0 */6 * * * /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/whitelist_governance_round.sh >> /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/logs/whitelist_governance_round.log 2>&1
```

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/eval/v6k_2a/scheduler_evidence.json` | External scheduler evidence |
| `artifacts/eval/v6k_2a/alert_governance_consistency_report.json` | Consistency check results |
| `artifacts/eval/v6k_2a/whitelist_operations_report.md` | Final operations report |

## Final Verdict

✅ **正式通过**

- External scheduler evidence: PASS
- Alert-governance consistency: PASS
- All consistency checks: PASS
- All tests: 24 passed

---

**Generated:** 2026-03-16
**Version:** v6k.2a
