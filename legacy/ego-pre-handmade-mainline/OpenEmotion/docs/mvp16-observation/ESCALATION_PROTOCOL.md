# MVP16 Observation Escalation Protocol

## Alert Thresholds

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| continuity_score | ≥ 0.8 | 0.6-0.8 | < 0.6 |
| identity_stability | ≥ 0.95 | 0.90-0.95 | < 0.90 |
| governance_compliance | = 1.0 | - | < 1.0 |
| invariant_violations | = 0 | - | > 0 |

## Escalation Levels

### Level 1: Warning
- Single metric in warning range
- Action: Log, continue monitoring
- No immediate intervention needed

### Level 2: Critical
- Any metric in critical range
- Multiple metrics in warning range
- Action: Generate ALERT, prepare blocker package

### Level 3: Emergency
- governance_compliance < 1.0
- invariant_violations > 0
- Action: Stop observation, immediate review

## Anomaly Response

When anomaly detected:

1. **Stop**: Do not continue "silent pass"
2. **Log**: Write ALERT to artifacts/mvp16-observation/ALERT.txt
3. **Analyze**: Root cause, impact, rollback need
4. **Package**: Create blocker package

## Required Anomaly Output

```markdown
# MVP16 Anomaly Report

## Summary
- What happened
- When detected
- Current status

## Root Cause Analysis
- Primary cause
- Contributing factors
- Evidence

## Impact Assessment
- Scope: [continuity|identity|governance|replay]
- Severity: [warning|critical|emergency]
- Trend: [improving|stable|worsening]

## Rollback Assessment
- Need rollback: [yes|no|maybe]
- Rollback target: [specific state]
- Rollback risk: [low|medium|high]

## Minimal Fix Chain
1. Step 1
2. Step 2
3. Step 3

## Blocker Package
- Path: artifacts/mvp16-observation/blocker_N.md
- Status: [pending|resolved]
```

## Human Intervention Points

| Day | Type | Action |
|-----|------|--------|
| Day 7 | Mid-term review | Assess week 1, adjust if needed |
| Day 14 | Final review | Assess full period, decide next |
| Any | Anomaly | Immediate review required |

## Contact Points

- Project: OpenEmotion / emotiond
- Repository: feature-emotiond-mvp
- Status File: roadmap/ROADMAP_STATE.json
- Handoff: artifacts/handoff/LATEST_HANDOFF.md
