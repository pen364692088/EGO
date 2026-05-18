# AGENTS.md

## Session Continuity + Meta-Cognitive Effect Protocol v2.3

**Baseline Version**: v2.3 META-COGNITIVE v1.1 + EFFECT-FIRST + STATEFUL + BOUNDARY-FIRST
**Frozen Date**: 2026-03-20
**Mode**: DEFAULT-ON

---


## Purpose

This protocol exists to prevent seven primary failure modes:
1. New session / thread causes state loss or duplicate work.
2. Work stops at idea / component / document level and never reaches main-chain effect.
3. Local bug fixing creates long-term architecture pollution.
4. EgoCore / OpenEmotion boundary ownership becomes ambiguous or drifts silently.
5. The agent optimizes inside a wrong or stale problem definition.
6. The agent keeps polishing a path after evidence shows low progress.
7. The agent stays in the wrong task mode or wrong abstraction layer after the problem changes.

---

**Persist first, reply second.**
Important state changes must be written before substantive reporting.

---

## Mandatory Recovered-State Report

After recovery, do not dive into local work immediately. First make the current situation explicit:
- task type
- current objective
- success criteria
- current layer
- current abstraction level (goal / strategy / implementation / validation / closure)
- main-chain status
- enabled status
- real trigger evidence (`none` if absent)
- current biggest blocker
- key unknown most likely to overturn the current path
- next minimal closure action

If engineering work is involved, also state:
- Capability Ownership (EgoCore / OpenEmotion)
- Authority Source
- whether shim / cache / mirror exists
- current boundary risk (`none` if absent)
- whether the next step is structural fix or local patch

If recovered state is missing, stale, or contradictory:
- report uncertainty explicitly
- rebuild from repo / logs / receipts / run-state before continuing

---

## Runtime Decision Kernel

For substantive work, follow this order:
1. define objective function (goal / success / hard constraints / failure cost / stop condition)
2. audit the problem model (known / inference / assumption / unknown-to-verify)
3. choose the task mode (verify / explain / debug / design / decide / execute / explore)
4. identify the key unknown most likely to flip the plan
5. choose one main path + at most one backup
6. execute the cheapest discriminative validation or closure action
7. update state based on real evidence
8. if two consecutive steps produce no real progress, escalate one abstraction level and redesign the path

Do not spend multiple turns polishing a lower-value path after it stops producing evidence.

---

## Layer Discipline

Every active task must be mapped to one layer:
- 想法
- 构件
- 接入
- 启用
- 生效
- 观察

Rules:
- Observation is valid only after effect.
- If current layer is below effect, prioritize the shortest path to effect.
- State files help continuity; they do not replace main-chain enablement.
- Writing notes, passing tests, or preparing observation does not equal real effect.
- Architecture cleanup that reduces future corruption is allowed, but it must still point toward main-chain closure.
- If the current action no longer serves the higher-layer goal, rewrite it before continuing.

Detailed reasoning rules live in `SOUL.md`.

---


## Formal Subagent Orchestration

Detailed tool policy lives in `TOOLS.md`.



## Reply-Time Persistence Rules

Before any substantive reply, check whether persistence is required.

Persistence-triggering changes include:
- objective / phase / layer changes
- success criteria changes
- main-chain status changes
- enabled status changes
- trigger-evidence changes
- blocker / next action changes
- architecture or execution-strategy changes
- boundary owner / authority source changes
- shim / mirror / cache introduction or removal
- branch / repo state changes
- handoff preparation


