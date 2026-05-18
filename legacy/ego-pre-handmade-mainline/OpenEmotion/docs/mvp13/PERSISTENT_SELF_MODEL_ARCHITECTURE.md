# Persistent Self-Model Architecture

## 1. Objective

The persistent self-model stores stable and semi-stable internal
representations about the system's identity, tendencies, constraints,
history-linked interpretations, and developmental continuity.

## 2. Component Layout

self_model/
    self_model_store.py
    self_model_types.py
    self_model_manager.py
    self_model_diff.py
    self_model_replay.py
    self_model_audit.py

## 3. Data Sources

The self-model may be updated from:
- developmental cycle summaries
- SRAP-aligned internal interpretations
- narrative memory summaries
- long-horizon task patterns
- verified behavioral traces

## 4. Data Sinks

The self-model may influence:
- candidate generation priors
- internal tension weighting
- memory relevance scoring
- continuity-aware evaluation

It MUST NOT directly control final user-facing replies.

## 5. State Classes

Suggested categories:
- stable identity traits
- semi-stable dispositions
- current tensions
- long-horizon commitments
- capability boundaries
- governance boundaries
- recent significant transitions

## 6. Versioning

Every self-model update must produce:
- model_version
- diff record
- timestamp
- update source
- trace reference
- replay token or replay seed
