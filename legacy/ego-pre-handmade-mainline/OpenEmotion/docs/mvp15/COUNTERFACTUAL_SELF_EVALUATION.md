# Counterfactual Self-Evaluation

## 1. Purpose

Counterfactual self-evaluation allows the system to compare
actual trajectories with plausible alternative trajectories.

## 2. Target Questions

Examples:
- What if a different drive resolution had been chosen?
- What if a self-model update had been deferred?
- What if a maintenance action had been prioritized earlier?
- What if a high-confidence self-claim had remained tentative?

## 3. Counterfactual Constraints

Counterfactual analysis must:
- be linked to real baseline traces
- use explicit assumptions
- record uncertainty
- avoid presenting speculation as fact

## 4. Output Classes

Suggested outputs:
- better-than-actual
- worse-than-actual
- uncertain
- governance-blocked alternative
- insufficient-evidence alternative

## 5. Use Cases

Counterfactual analysis may support:
- error diagnosis
- revision proposal generation
- self-model calibration
- drive policy adjustment
- maintenance priority refinement

## 6. Required Artifacts

artifacts/mvp15/
counterfactual_runs.json
reflection_reports.json
revision_candidates.json
