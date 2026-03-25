# MVP11 Hard Gate Report

**Mode**: `shadow`
**Overall Status**: `✅ PASS`
**Entries Analyzed**: `0`
**Date Range**: `N/A` to `N/A`
**Threshold Source**: `calibrated`

## Threshold Calibration

- **Path**: `reports/mvp11_threshold_calibration.json`
- **Generated**: `2026-03-05T08:08:24.481974`
- **Samples**: 1 entries

## Gate Results

| Gate | Status | Threshold | Observed | Reason |
|------|--------|-----------|----------|--------|
| replay_hash_match | ✅ PASS | 1.000 | - | hash_match_rate >= 1.000 for all entries |
| sanity_consecutive | ⚠️ UNKNOWN | 2 days | - | No entries |
| concentration_consecutive | ⚠️ UNKNOWN | 0.550 / 2d | - | No entries |
| bias_consecutive | ⚠️ UNKNOWN | 0.120 / 2d | - | No entries |

## Thresholds Used

| Threshold | Value | Source |
|-----------|-------|--------|
| replay_hash_match_rate | 1.0000 | default |
| sanity_consecutive_days | 2 | calibrated (insufficient) |
| concentration_top1_threshold | 0.5500 | default |
| concentration_consecutive_days | 2 | default |
| bias_p95_threshold | 0.1200 | calibrated (insufficient) |
| bias_consecutive_days | 2 | default |

## Testbot E2E Gates (Shadow Mode)

**Overall Status**: `PASS`

- **Scenarios**: 3 total, 0 failed
- **Tape Hash Match**: `True`
- **Phi Top1 Share**: `0.281`
- **Unique Signatures**: `14`

| Gate | Status | Value | Threshold | Reason |
|------|--------|-------|-----------|--------|
| tape_hash_match | ✅ PASS | True | - | All scenarios replay hash matched |
| phi_top1_share | ✅ PASS | 0.281 | 0.600 | phi_top1_share=0.281 <= threshold=0.600 |
| unique_signatures | ✅ PASS | 14 | 5 | unique_signatures=14 >= floor=5 |