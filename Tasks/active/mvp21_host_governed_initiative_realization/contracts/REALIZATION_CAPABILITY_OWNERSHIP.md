# WP16 / MVP21 Realization Capability Ownership

## OpenEmotion Owns

- initiative realization semantics
- initiative realization state
- commitment fulfillment state
- proactive readiness state
- realization hold state
- delivery readiness snapshot semantics
- host lane hint semantics
- controlled delivery candidate semantics
- initiative realization audit / ledger
- formal owner target: `OpenEmotion/openemotion/initiative_realization/*`

## OpenEmotion Does Not Own

- direct reply authority
- tool execution authority
- transport execution authority
- host proactive enable policy
- proactive delivery / outbox / transport substrate
- runtime scheduling
- real-world execution / risk adjudication

## Upstream Owners Stay Authoritative

`WP16` 不抢走以下 formal owner：

- `OpenEmotion/openemotion/initiative_self/*`
- `OpenEmotion/openemotion/selfhood_integration/*`
- `OpenEmotion/openemotion/self_model/*`
- `OpenEmotion/openemotion/endogenous_drives/*`
- `OpenEmotion/openemotion/reflective_self/*`
- `OpenEmotion/openemotion/developmental_self/*`
- `OpenEmotion/openemotion/social_self/*`
- `OpenEmotion/openemotion/embodied_self/*`

## EgoCore Keeps

- runtime / scheduler / proactive delivery / outbox / transport substrate
- outward response contract
- ask / wait / block / escalate
- trace / replay / gate / audit / maintenance ledger
- real-world execution and risk adjudication

## Phase 1 Scope Boundary

- owns: semantic readiness / fulfillment / realization interpretation, bounded delivery-readiness proposals, bounded host-lane mediation hints
- does not own: proactive send authority, outbox enqueue authority, transport enablement, direct response-plan injection, or any live authority release
