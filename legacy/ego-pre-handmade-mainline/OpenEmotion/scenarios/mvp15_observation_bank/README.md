# MVP15 Observation Scenario Bank

This bank is the formal entry point for `WP10/MVP15` controlled observation samples.

Each manifest must:
- use `schema_version = mvp15.observation_scenario.v1`
- declare one of `open_license | user_owned | repo_authored`
- provide `messages` plus structured runtime hints
- provide an `owner_bootstrap` only as seed input, not as evidence
- avoid embedding any success claim in the manifest itself

Formal evidence is produced only after the manifest is executed through:

`runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`

and then results in:
- governed `reflective_self_writeback`
- formal owner revision creation
- replay-valid owner state
- proposal-only discipline preserved

Raw manifests are not evidence.
