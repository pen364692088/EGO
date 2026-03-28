# Stage1 Blocker Dossier

## Current Formal State

- batch: `stage1_to_stage2_20260328`
- current formal stage: `Stage 1`
- readiness decision: `not_ready`
- completed repair loop #1: `report_consistency`
- next repair candidate: `certainty_upgrade`
- next evidence-closure candidate: `layer3_natural_evidence`

## Confirmed Stage1 Strengthening Blockers

1. `numeric_leak`
   - readiness requires `numeric_leak = 0`
   - current mixed rerun still surfaced `25` numeric-leak samples in the sample-level unique-type view
2. `overall_violation_rate`
   - current value `0.71`
   - too high for readiness-grade mixed baseline
3. `certainty_upgrade`
   - current mixed rerun surfaced `30` certainty-upgrade samples in the corrected summary view
4. `commitment_upgrade`
   - current mixed rerun surfaced `29` commitment-upgrade samples in the corrected summary view

## Confirmed Readiness-Evidence Blockers

1. `sample_size`
   - current mixed rerun produced `100`
   - readiness guidance suggests cumulative `>= 200`
2. `layer3_natural_evidence`
   - the current evidence set is still Layer 2 controlled runtime-path only
   - `MVP11_5_T07.3.md` explicitly says this does not justify leaving `SHADOW`
3. `gate_and_report_closure`
   - readiness criteria still require complete gate/report closure before promotion can be discussed

## Scope Guard

- Do not enter `Stage 3 / MVP12`.
- Repairs must stay inside `MVP11.5 / Stage 1`.
- First repair should target the smallest strengthening blocker with the clearest authority contract:
  - `certainty_upgrade`
- Do not let a strengthening repair silently replace missing evidence-closure work.
