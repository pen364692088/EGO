# MVP13 Observation Scenario Bank

这些 manifest 不是证据本身。

正式证据只来自：

- formal runtime ingress/egress
- `developmental_tick`
- formal owner writeback
- revision / replay / gate verdict

本目录只提供受控 observation 输入语料。允许来源：

- `repo_authored`
- `user_owned`
- `open_license`

不允许：

- 无许可网页抓取
- 把 raw corpus 直接当成 `E4/E5`
- 绕过 `run_mvp13_controlled_observation` 主链

## Current Scenarios

| scenario_id | source_class | source_ref | target |
| --- | --- | --- | --- |
| `repo_authored_continuity_gap` | `repo_authored` | repo local | `continuity_gap` |
| `open_license_ultrachat_tracking` | `open_license` | `HuggingFaceH4/ultrachat_200k` | `mechanism_gap` |
| `open_license_oasst1_monopsony` | `open_license` | `OpenAssistant/oasst1` | `definition_gap` |
