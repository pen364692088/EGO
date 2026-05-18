# Reflective Self Architecture

## 1. Objective

The reflective self layer allows the system to analyze its own
state transitions, decisions, drive activations, self-model revisions,
and developmental trajectories.

## 2. Component Layout

reflection/
    reflection_engine.py
    reflection_types.py
    self_diagnosis.py
    counterfactual_runner.py
    revision_proposer.py
    reflection_audit.py

## 3. Reflection Targets

The reflection layer may analyze:
- self-model revisions
- drive conflict resolutions
- maintenance outcomes
- candidate selection patterns
- repeated failure modes
- continuity breaks
- unresolved tensions

## 4. Reflection Outputs

The layer may produce:
- diagnosis reports
- revision proposals
- counterfactual comparisons
- confidence adjustments
- flagged uncertainty zones

These outputs MUST NOT directly overwrite policy or governance.

## 5. Data Dependencies

Reflection depends on:
- replay traces
- self-model history
- drive state history
- maintenance audits
- response-plan evidence
