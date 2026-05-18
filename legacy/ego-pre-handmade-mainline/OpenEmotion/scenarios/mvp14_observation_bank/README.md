# MVP14 Observation Scenario Bank

This bank is the formal entry point for `WP9/MVP14` controlled observation samples.

Each manifest must:
- use `schema_version = mvp14.observation_scenario.v1`
- declare one of `open_license | user_owned | repo_authored`
- provide `messages` plus structured runtime hints
- avoid embedding any success claim in the manifest itself

The formal evidence is still produced only after the manifest is executed through:

`runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`

and then results in:
- governed `endogenous_drive_writeback`
- formal owner revision creation
- replay-valid owner state

Raw manifests are not evidence.
