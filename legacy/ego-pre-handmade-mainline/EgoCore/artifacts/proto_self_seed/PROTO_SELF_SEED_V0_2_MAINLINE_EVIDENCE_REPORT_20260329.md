# Proto-Self Seed v0.2 Mainline Evidence Report

- date: `2026-03-29`
- scope: `repo-level V4 mainline proof`
- boundary: `formal Telegram mainline wiring only; no live Telegram E4/E5 claim in this report`

## Authority Source

- `Tasks/Proto-Self_Seed/Proto-Self_Seed_v0.2_正式设计稿.md`
- `Tasks/Proto-Self_Seed/README.md`
- current formal mainline seam:
  - `telegram_bot -> native_loop -> native_hooks -> runtime_v2/proto_self_runtime -> openemotion_adapter -> openemotion.proto_self_v2`

## Profile / Entry

- envelope schema: `proto_self.v2`
- explicit profile: `subject_profile = "seed_v0_2"`
- rollout control: `seed_v0_2` remains explicit opt-in; base `proto_self.v2` path stays default

## Repo-Tracked Evidence Artifact

- sample directory:
  - `EgoCore/artifacts/proto_self_seed/repo_v4_mainline_seed/sample_20260329_135400_c47a3ba2`
- ledger:
  - `EgoCore/artifacts/proto_self_seed/repo_v4_mainline_seed/sample_20260329_135400_c47a3ba2/ledger.json`

## Mainline Facts Proven

- ingress normalized event persisted with:
  - `inputs.normalized_event.schema_version == "proto_self.v2"`
  - `inputs.normalized_event.subject_profile == "seed_v0_2"`
- OpenEmotion result persisted with:
  - `openemotion.result.schema_version == "proto_self.output.v2"`
  - `openemotion.result.subject_profile == "seed_v0_2"`
  - `openemotion.result.candidate_actions == ["inspect_file", "write_file"]`
- trace persisted with:
  - `openemotion.trace_payload.schema_version == "proto_self.trace.v2"`
  - `openemotion.trace_payload.subject_profile == "seed_v0_2"`
- host response plan persisted with:
  - `host.response_plan.proto_self_subject_profile == "seed_v0_2"`
- same sample includes separated subject/host stages:
  - `kernel_output`
  - `ingress_kernel_trace`
  - `finalized_result_kernel_trace`
  - `idle_check_kernel_trace`

## Candidate vs Final Action Boundary

- subject side emits `candidate_actions`
- host side still owns final delivery / terminal result
- the same ledger shows:
  - ingress candidate stage
  - finalized-result feedback writeback
  - post-turn idle-check writeback
- this is the repo-level proof that `candidate != execution`

## Validation Commands

```bash
python3 -m py_compile \
  OpenEmotion/openemotion/proto_self_v2/__init__.py \
  OpenEmotion/openemotion/proto_self_v2/kernel.py \
  OpenEmotion/openemotion/proto_self_v2/schemas.py \
  OpenEmotion/openemotion/proto_self_v2/state.py \
  OpenEmotion/openemotion/proto_self_v2/trace_types.py \
  OpenEmotion/openemotion/proto_self_v2/seed_schemas.py \
  OpenEmotion/openemotion/proto_self_v2/seed_state.py \
  OpenEmotion/openemotion/proto_self_v2/seed_affordances.py \
  OpenEmotion/openemotion/proto_self_v2/seed_governor_lite.py \
  OpenEmotion/openemotion/proto_self_v2/seed_kernel.py \
  OpenEmotion/openemotion/proto_self_v2/tests/test_seed_profile_contract.py \
  EgoCore/app/openemotion_adapter/proto_self_adapter.py \
  EgoCore/app/openemotion_adapter/proto_self_contract_validator.py \
  EgoCore/app/openemotion_adapter/proto_self_state_store.py \
  EgoCore/app/openemotion_hooks/native_hooks.py \
  EgoCore/app/runtime_v2/proto_self_runtime.py \
  EgoCore/app/runtime_v2/state.py \
  EgoCore/app/runtime_v2/decision_engine.py \
  EgoCore/app/telegram_bot.py \
  EgoCore/app/command_router.py \
  EgoCore/tests/test_proto_self_v2_contracts.py \
  EgoCore/tests/test_proto_self_state_store.py \
  EgoCore/tests/test_runtime_v2_proto_self_runtime.py \
  EgoCore/tests/test_telegram_session_commands.py \
  EgoCore/tests/test_telegram_proto_self_v2_evidence.py
```

```bash
PYTHONPATH=OpenEmotion:EgoCore ./EgoCore/.venv/bin/python -m pytest -s -q \
  OpenEmotion/openemotion/proto_self_v2/tests/test_kernel_contract.py \
  OpenEmotion/openemotion/proto_self_v2/tests/test_seed_profile_contract.py \
  EgoCore/tests/test_proto_self_v2_contracts.py \
  EgoCore/tests/test_proto_self_state_store.py \
  EgoCore/tests/test_runtime_v2_proto_self_runtime.py \
  EgoCore/tests/test_telegram_session_commands.py \
  EgoCore/tests/test_telegram_proto_self_v2_evidence.py
```

## Conclusion

- completion strength: `repo-level V4 achieved`
- not claimed here:
  - real Telegram live rollout
  - multi-sample stability
  - Seed replacing default `proto_self.v2` path
