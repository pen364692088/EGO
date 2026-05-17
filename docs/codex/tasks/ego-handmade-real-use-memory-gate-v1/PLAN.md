# Ego Handmade Real Use Memory Gate v1 - PLAN

## Implementation

- extend `OperatorMemoryStore` with candidate memory, memory event log, hot
  context selection, cold archive, and operator memory management operations
- expose CLI commands: `/memory_review`, `/memory_pin`, `/memory_unpin`,
  `/memory_archive`, and `/forget`
- inject hot memory into prompt only through `MemoryContext`, with candidate
  memory excluded until pinned, repeatedly hit, or task-relevant
- add a deterministic real-use gate runner with 10+ practical operator
  scenarios and JSON/Markdown reports

## Validation

- add layered-memory tests for candidate/core/hot/cold boundaries
- add real-use gate tests for report shape, scenario coverage, memory hits,
  tool gate behavior, and no memory misuse
- rerun existing `Ego_handmade` operator/memory/permission/comparison tests
- run syntax checks and scoped diff checks

## Rollback

Revert the `Ego_handmade` memory/gate/runner changes plus this task directory.
Runtime memory and real-use reports are ignored local artifacts.
