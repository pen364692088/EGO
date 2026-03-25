# Developmental Core Architecture

## 1. Core Components

developmental_core/
    cycle_engine.py
    hypothesis_generator.py
    candidate_evaluator.py
    cycle_memory.py

## 2. Cycle Engine

The cycle engine periodically generates internal reasoning cycles.

Trigger sources:

- idle cycles
- unresolved tensions
- long-term goal pressure
- replay events

## 3. Candidate Types

The core may produce:

- interpretation candidates
- action candidates
- explanation candidates
- self-model hypotheses

Each candidate must include:

id
timestamp
origin_cycle
confidence
trace_reference
