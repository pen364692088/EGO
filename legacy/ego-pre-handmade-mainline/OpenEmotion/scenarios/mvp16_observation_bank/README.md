# MVP16 Observation Bank

This bank contains controlled developmental-continuity scenarios for `WP11/MVP16`.

Rules:
- Raw scenario files are not evidence on their own.
- A scenario only counts after it is executed through the formal runtime harness via
  `run_mvp16_controlled_observation.py` or `run_mvp16_controlled_observation_batch.py`.
- Allowed `source_class` values are:
  - `open_license`
  - `user_owned`
  - `repo_authored`
- Current bank is seeded with `repo_authored` scenarios only.
