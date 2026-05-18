# MVP12 — Developmental Core Sandbox

## 1. Purpose

MVP12 introduces a developmental core capable of generating
internal cycles independent of immediate user input.

The goal is not to produce final behavior,
but to create an internal candidate generation system.

## 2. Key Principles

- Internal activity must be observable and traceable
- Developmental core does NOT control final responses
- Governor and SRAP layers remain authoritative
- All outputs are treated as "candidates"

## 3. Architectural Position

Layer structure:

Layer 1 — Governance Shell  
Layer 2 — Proto-Self (emotiond / SRAP)  
Layer 3 — Developmental Core Sandbox

The developmental core runs beneath the governance shell
and cannot bypass it.

## 4. Allowed Capabilities

The developmental core may generate:

- internal hypotheses
- candidate actions
- candidate interpretations
- internal tensions
- long-horizon goals

## 5. Forbidden Capabilities

The developmental core MUST NOT:

- produce final replies directly
- modify SRAP contract rules
- bypass Governor v2
- persist long-term state without audit trail

## 6. Output Channels

Outputs must go through:

developmental_trace → candidate_pool → evaluation layer

## 7. Expected Artifacts

artifacts/mvp12/

developmental_cycles.json
candidate_pool.json
sandbox_metrics.json
cycle_traces/
