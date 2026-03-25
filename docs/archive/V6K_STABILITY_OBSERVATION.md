# v6k Stability Observation Period

## Period

**Start:** 2026-03-16
**End:** 2026-03-30
**Duration:** 14 days

## Purpose

Observe production whitelist governance stability after v6k line completion.

## Daily Check

**Script:** `tools/v6k_daily_stability_check.sh`

**Install (optional):**
```bash
# Add to crontab for daily automated check
crontab -e
# Add:
# 5 4 * * * /path/to/OpenEmotion/tools/v6k_daily_stability_check.sh >> logs/v6k_stability.log 2>&1
```

**Manual run:**
```bash
./tools/v6k_daily_stability_check.sh
```

## Metrics

| Metric | Threshold | Notes |
|--------|-----------|-------|
| critical_alerts | < 3 | More than 3 = ACTION_REQUIRED |
| stability_score | 1.0 | 0.5 = OBSERVE, 0.0 = ACTION_REQUIRED |
| scheduler_runs | > 0 | Must have at least 1 run |
| governance_verdict | stable/observe | Track verdict drift |

## Verdict Levels

| Verdict | Condition | Action |
|---------|-----------|--------|
| BOOTSTRAP | no observation data yet | Continue observation, **does not count toward exit criteria** |
| STABLE | critical_alerts = 0 | Continue observation, counts toward exit |
| OBSERVE | 0 < critical_alerts < 3 | Monitor closely, counts toward exit |
| ACTION_REQUIRED | critical_alerts >= 3 | Investigate root cause, resets exit counter |

## Daily Log

| Day | Date | Critical | Warning | Score | Verdict | Notes |
|-----|------|----------|---------|-------|---------|-------|
| 1 | 2026-03-17 | 0 | 0 | 1.0 | BOOTSTRAP | No observation data yet (does not count toward exit) |
| 2 | 2026-03-18 | - | - | - | - | Pending |

## Exit Criteria

- **14 consecutive days of STABLE or OBSERVE verdicts**
- **BOOTSTRAP days do NOT count toward the 14-day requirement**
- No regression in governance verdicts
- All 4 production whitelist scenarios must have real observation data

---

**Last Updated:** 2026-03-17
