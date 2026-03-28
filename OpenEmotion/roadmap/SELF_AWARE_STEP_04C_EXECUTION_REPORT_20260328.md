# SELF_AWARE_STEP_04C — MVP13 Contract Convergence

## Summary

Step04C resolves the remaining contract split inside the formal MVP13 owner.

The key result is not a behavioral proof. The key result is that the formal
owner contract is now converged on `openemotion/self_model/*` plus
`schemas/self_model.schema.json`, so future proof work no longer needs to rely
on `emotiond/self_model/*` as the semantic owner.

## What Changed

- `openemotion/self_model/model.py` and `schemas/self_model.schema.json` now
  agree on the canonical identity field: `identity_handle`
- the formal owner now emits the required metadata fields:
  - `schema_version`
  - `modification_audit_trail`
- the formal schema now matches the owner representation for
  `confidence_by_domain` (`object` / `domain -> confidence`)
- `current_mode` has been removed from the formal owner schema because it
  belongs to transient proto-self/runtime state, not MVP13 persistent
  self-model authority
- MVP13 stage docs and version spec now point to `openemotion/self_model/*`
  as the only formal owner
- legacy `emotiond/self_model/*` structures are explicitly downgraded to
  historical / migration / comparative evidence

## Converged Formal Owner Contract

The converged Step04C contract is:

- `schema_version`
- `identity_handle`
- `capabilities`
- `limitations`
- `active_goals`
- `standing_commitments`
- `tool_authority_boundary`
- `dependency_map`
- `confidence_by_domain`
- `known_unknowns`
- `created_at`
- `last_modified_at`
- `modification_audit_trail`

## What Was Explicitly Demoted

The following fields or structures are no longer treated as Step04C formal
owner contract fields:

- `identity_core`
- `stable_constraints`
- `behavioral_tendencies`
- `active_tensions`
- `long_horizon_orientations`
- `continuity_trace`
- `revision_history`
- `SelfModelManager`

They remain useful as historical evidence or migration candidates, but they
cannot be used as the authoritative MVP13 contract for future promotion claims.

## Verification

- `./EgoCore/.venv/bin/python -m py_compile OpenEmotion/openemotion/self_model/model.py`
- `PYTHONPATH=OpenEmotion ./EgoCore/.venv/bin/python -m pytest -s -q OpenEmotion/tests/mvp13/test_self_model_owner_contract.py`
  - `4 passed`
- `PYTHONPATH=OpenEmotion ./EgoCore/.venv/bin/python -m pytest -s -q OpenEmotion/tests/mvp13/test_self_model_infra.py OpenEmotion/tests/mvp13/test_integration.py OpenEmotion/tests/mvp13/test_e2e_gate_b.py`
  - `58 passed`

## Formal Conclusion

Step04C is complete as a contract-convergence step.

This does **not** prove MVP13 behavioral influence.

It proves only that future behavioral influence proof now has a unique
formal owner and a converged base contract.

## Next Action

Proceed to `SELF_AWARE_STEP_04D` and design a governed, replayable behavioral
influence proof that intervenes only on Step04C-authorized owner fields.
