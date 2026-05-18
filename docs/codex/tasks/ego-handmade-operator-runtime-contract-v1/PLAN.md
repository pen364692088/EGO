# Ego Handmade Operator Runtime Contract v1 - PLAN

## Implementation

- Add runtime mode handling and permission status output.
- Add a candidate-local permission broker for file-write proposals, operator
  decisions, one-shot leases, and traceable execution.
- Add CLI commands for `/mode`, `/approvals`, `/approve`, `/reject`, and
  `/edit_approval`.
- Downgrade subagents to read-only tools; side-effect work must return a
  proposed action to the main agent.
- Record runtime mode and pending approvals in trace.

## Verification

- Add focused tests for modes, approval flow, lease path/hash checks, overwrite
  gate, write allowlist, subagent side-effect denial, and trace output.
- Run existing Ego_handmade targeted tests.
- Run syntax checks and scoped diff check.

## Closeout

- Update `STATUS.md` with local candidate evidence.
- Commit and push only scoped `Ego_handmade/**` and task docs.
