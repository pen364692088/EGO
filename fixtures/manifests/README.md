# Regression Manifests

These manifests serve as regression baselines. Any changes to emotiond core logic, appraisal, or decision-making should not change the output hashes.

## Manifests

| File | Description | Key Verification |
|------|-------------|------------------|
| care_sequence.json | Single care event | action should be approach/repair_offer |
| betrayal_sequence.json | Single betrayal event | action should be withdraw/boundary |
| mixed_sequence.json | Care → Betrayal → Apology | decision should change across sequence |

## Usage

```bash
# Verify all manifests still produce consistent results
for manifest in fixtures/manifests/*.json; do
  ./tools/replay_manifest.sh "$manifest"
done
```

## Adding New Manifests

When adding new regression cases:
1. Generate manifest: `./tools/test_emotiond_deterministic.sh ... --manifest new_case.json`
2. Move to fixtures/manifests/
3. Document expected behavior in this README
