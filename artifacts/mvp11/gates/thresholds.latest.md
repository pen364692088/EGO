# MVP11.4.7 Threshold Calibration Report

**Generated**: 2026-03-05T14:57:36.192845+00:00
**Commit**: 194100b
**Confidence**: medium
**Source Window**: 30 days
**Frozen**: thresholds.20260305T145736Z.json

**Total Entries Analyzed**: 30
**Nightly Summaries**: 30
**Trend Entries**: 0

## Summary

- **Thresholds to Review**: 5
- **Insufficient Data**: 6

## Hard Gates

| Threshold | Current | Recommended | Status | Confidence |
|-----------|---------|-------------|--------|------------|
| replay_hash_match_rate | 1.0 | 1.0 | OK | high |
| sanity_consecutive_days | 2 | 2 | OK | medium |
| concentration_top1_threshold | 0.55 | 0.415077 | REVIEW | high |
| bias_p95_threshold | 0.12 | 0.109577 | REVIEW | high |

## Soft Thresholds

| Threshold | Current | Recommended | Status | Confidence |
|-----------|---------|-------------|--------|------------|
| concentration_hhi_threshold | 0.25 | 0.088297 | REVIEW | high |
| sanity_ok_rate_min | 0.99 | 0.99 | NO_DATA | insufficient |
| drift_alert_threshold | 0.2 | 0.2 | NO_DATA | insufficient |
| bias_near_cap_rate | 0.05 | 0.05 | NO_DATA | insufficient |

## Gate Parameters

| Parameter | Current | Recommended | Status |
|-----------|---------|-------------|--------|
| max_governor_delta | 0.01 | 0.01 | NO_DATA |
| max_drift_delta | 0.01 | 0.01 | NO_DATA |
| min_sanity_ok_rate | 0.99 | 0.99 | NO_DATA |

## Cycle Graph Limits

| Limit | Current | Recommended | Status |
|-------|---------|-------------|--------|
| max_nodes | 10000 | 567 | REVIEW |
| max_edges | 50000 | 1687 | REVIEW |

## Rationale for Reviews

### concentration_top1_threshold

- **Current**: `0.55`
- **Recommended**: `0.415077`
- **Rationale**: Based on mean=0.2260, std=0.0757, p95=0.3374; added 10.0% margin
- **Stats**: mean=0.2260, std=0.0757, p95=0.3374, n=29

### bias_p95_threshold

- **Current**: `0.12`
- **Recommended**: `0.109577`
- **Rationale**: Based on mean=0.0660, std=0.0168, p95=0.0893; added 10.0% margin
- **Stats**: mean=0.0660, std=0.0168, p95=0.0893, n=30

### concentration_hhi_threshold

- **Current**: `0.25`
- **Recommended**: `0.088297`
- **Rationale**: Based on mean=0.0517, std=0.0143, p95=0.0773; added 10.0% margin
- **Stats**: mean=0.0517, std=0.0143, p95=0.0773, n=29

### max_nodes

- **Current**: `10000`
- **Recommended**: `567`
- **Rationale**: Based on mean=285.2333, std=115.2391, p95=463.7500; added 10.0% margin
- **Stats**: mean=285.2333, std=115.2391, p95=463.7500, n=30

### max_edges

- **Current**: `50000`
- **Recommended**: `1687`
- **Rationale**: Based on mean=773.0000, std=380.6458, p95=1370.6500; added 10.0% margin
- **Stats**: mean=773.0000, std=380.6458, p95=1370.6500, n=30

## Observed Statistics

### sanity_ok_coverage

- n: 30, mean: 0.9667, std: 0.1826
- min: 0.0000, max: 1.0000
- p5: 1.0000, p50: 1.0000, p95: 1.0000

### bias_p95

- n: 30, mean: 0.0660, std: 0.0168
- min: 0.0317, max: 0.1066
- p5: 0.0416, p50: 0.0666, p95: 0.0893

### bias_mean

- n: 30, mean: 0.0467, std: 0.0133
- min: 0.0222, max: 0.0897
- p5: 0.0291, p50: 0.0466, p95: 0.0625

### near_cap_rate

- n: 30, mean: 0.0237, std: 0.0099
- min: 0.0000, max: 0.0388
- p5: 0.0103, p50: 0.0230, p95: 0.0378

### cycle_graph_nodes

- n: 30, mean: 285.2333, std: 115.2391
- min: 107.0000, max: 486.0000
- p5: 115.1500, p50: 285.5000, p95: 463.7500

### cycle_graph_edges

- n: 30, mean: 773.0000, std: 380.6458
- min: 237.0000, max: 1432.0000
- p5: 273.6000, p50: 743.5000, p95: 1370.6500

### cycle_store_count

- n: 30, mean: 107.5667, std: 44.5728
- min: 0.0000, max: 195.0000
- p5: 53.6000, p50: 104.0000, p95: 179.5500

### replay_hash_match_rate

- n: 29, mean: 1.0000, std: 0.0000
- min: 1.0000, max: 1.0000
- p5: 1.0000, p50: 1.0000, p95: 1.0000

### phi_top1_share

- n: 29, mean: 0.2260, std: 0.0757
- min: 0.1046, max: 0.3472
- p5: 0.1167, p50: 0.2226, p95: 0.3374

### phi_top3_share

- n: 29, mean: 0.4210, std: 0.0870
- min: 0.2859, max: 0.5846
- p5: 0.3081, p50: 0.4361, p95: 0.5641

### phi_hhi

- n: 29, mean: 0.0517, std: 0.0143
- min: 0.0316, max: 0.0782
- p5: 0.0341, p50: 0.0532, p95: 0.0773
