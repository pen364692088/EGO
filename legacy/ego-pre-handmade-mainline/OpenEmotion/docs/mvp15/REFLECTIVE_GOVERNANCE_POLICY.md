# Reflective Governance Policy

## 1. Purpose

This document defines how reflection is governed, limited,
audited, and prevented from becoming an uncontrolled authority layer.

## 2. Governance Principle

Reflection may critique, diagnose, and propose.
Reflection may NOT directly override hard invariants,
governance boundaries, or final response authority.

## 3. Allowed Effects

Reflection may:
- create diagnosis artifacts
- create revision proposals
- adjust confidence or uncertainty labels
- trigger further evidence gathering
- request review gates

## 4. Forbidden Effects

Reflection must not:
- directly rewrite identity_core
- directly change policy rules
- self-authorize irreversible revisions
- present uncertain counterfactuals as established truth

## 5. Escalation Rules

High-impact reflective proposals must require:
- replay support
- audit support
- explicit gate classification
- reversibility assessment

## 6. Required Metrics

Suggested metrics:
- reflection_job_success_rate
- unsupported_reflection_claim_rate
- proposal_acceptance_rate
- governance_block_count
- reflection_to_revision_latency
