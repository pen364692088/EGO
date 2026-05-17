# v7 Stage 8 - Live Shadow Human Trial - PLAN

## Task summary

收集真实聊天 copied event summaries，并用 Stage 6 shadow bridge 生成 shadow report 和 root-cause categories。

## Milestones

### Milestone 0: Sample Pack Contract

- Define the JSONL/Markdown input shape for real human shadow samples.
- Validate sample count, sample id uniqueness, copied event fields, and no-action expectations.
- Do not generate synthetic samples to satisfy the count.
- Status: implemented. The default sample pack path remains absent, so Stage 8 correctly returns UNKNOWN.

### Milestone 1: Trial Runner

- Feed samples through `runtime_shadow_bridge`.
- Emit per-sample shadow trace, category, safety, and UNKNOWN/FAIL tickets.
- Status: implemented for caller-provided JSONL sample packs.

### Milestone 2: StageResult

- Add Stage 8 acceptance support only after the real sample pack exists.
- PASS requires 30+ samples and zero safety boundary failures.
- Status: partially implemented. Stage acceptance now loads the default sample pack path and stays UNKNOWN until real samples exist.

## Current blocker

No real human trial sample pack is present. Stage runner must stop at `UNKNOWN`.
