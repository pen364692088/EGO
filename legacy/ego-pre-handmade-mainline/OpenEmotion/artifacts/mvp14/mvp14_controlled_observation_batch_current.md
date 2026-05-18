# MVP14 Controlled Observation Batch Report

- generated_at: `2026-04-03T16:23:40.966252+00:00`
- git_commit_short: `7245f5f`
- report_count: `3`
- accepted_count: `3`
- replay_consistent_count: `3`
- maintenance_candidate_present_count: `3`
- invariant_violation_count: `0`
- distinct_targets: `['existing_debt_with_continuity_imbalance', 'repair_pressure_with_governed_maintenance', 'replay_debt_under_low_reserve']`
- source_breakdown: `{'repo_authored': 3}`
- verification_level: `V5`
- evidence_level: `E5`
- status: `pass`

## Scenarios

- `repo_authored_existing_debt_continuity` target=`existing_debt_with_continuity_imbalance` accepted=`True` candidate=`True` replay_valid=`True` dominant_drive=`stability`
- `repo_authored_low_reserve_replay` target=`replay_debt_under_low_reserve` accepted=`True` candidate=`True` replay_valid=`True` dominant_drive=`stability`
- `repo_authored_repair_pressure_guarded` target=`repair_pressure_with_governed_maintenance` accepted=`True` candidate=`True` replay_valid=`True` dominant_drive=`stability`

## Boundary

This aggregate report proves controlled multi-sample endogenous-drive writeback stability on the formal runtime mainline. It does not claim live autonomy, direct reply authority, or broader transport evidence.
