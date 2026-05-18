# v6j: Guard Drill Completion Report

## Drill Results

### Demotion Drill

| Item | Value |
|------|-------|
| **drill_type** | fallback_rate_overflow |
| **trigger** | fallback_rate > 10% |
| **result** | PASS |
| **expected_action** | demote |
| **actual_action** | demote |
| **expected_status** | demoted |
| **actual_status** | demoted |
| **fallback_rate** | 13.0% |
| **demotion_triggered** | True |

### Rollback Drill

| Item | Value |
|------|-------|
| **drill_type** | wrong_user_guard_trigger |
| **trigger** | wrong_user_guard_trigger_count > 0 |
| **result** | PASS |
| **expected_action** | rollback |
| **actual_action** | rollback |
| **expected_status** | rolled_back |
| **actual_status** | rolled_back |

## Summary

| Drill | Result |
|-------|--------|
| **demotion_drill** | PASS |
| **rollback_drill** | PASS |
| **all_passed** | True |

## Fixes Applied

1. **Fallback Rate Overflow Drill**
   - Fixed to capture demotion decision when triggered
   - Now correctly passes when status changes to DEMOTED

2. **Wrong User Guard Drill**
   - Already working correctly
   - Triggers ROLLBACK action immediately

3. **Promotion Receipt Linking**
   - Fixed `_load_state` to link promotion receipts to scenarios
   - This ensures rollback thresholds are correctly applied

## Verification

- 13 new v6j tests added
- 362 total tests passed
- System recoverable after drills

---

**Generated:** 2026-03-16
**Scenario:** complex_semantic_reasoning
