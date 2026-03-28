from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.dashboard.types import (
    ContinuityObservationRecord,
    DashboardBuildSummary,
    FailureIndexRecord,
    GrowthSignalRecord,
    RunIndexRecord,
)

EGO_ROOT = Path(__file__).resolve().parents[3]
REAL_TELEGRAM_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
FAILURE_CASES_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
DASHBOARD_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
OBSERVATION_DIR = EGO_ROOT / "artifacts" / "mvs_e5_observation"
VALIDATION_DOC = EGO_ROOT / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"

RUNS_FILE = "runs.jsonl"
CONTINUITY_FILE = "continuity_observation.jsonl"
GROWTH_FILE = "growth_signals.jsonl"
FAILURES_FILE = "failures.jsonl"
GAP_SUMMARY_FILE = "gap_summary.json"
BUILD_META_FILE = "build_meta.json"

REAL_CAPTURE_STATUS_DOC = "REAL_MAINLINE_CAPTURE_STATUS.md"
CONTINUITY_LEDGER_DOC = "CONTINUITY_OBSERVATION_LEDGER.md"
PLASTICITY_REFLECTION_DOC = "PLASTICITY_REFLECTION_EVIDENCE.md"
GAP_SUMMARY_DOC = "GAP_SUMMARY.md"
DATA_SCHEMA_DOC = "DATA_SCHEMA.md"
README_DOC = "README.md"

SAMPLE_ID_RE = re.compile(r"sample_\d{8}_\d{6}_[0-9a-f]{8}")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return _load_json(path)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(EGO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _iter_sample_dirs(real_dir: Path) -> List[Path]:
    if not real_dir.exists():
        return []
    return sorted(
        path for path in real_dir.iterdir() if path.is_dir() and path.name.startswith("sample_")
    )


def _artifact_refs(sample_dir: Path) -> Dict[str, str]:
    refs: Dict[str, str] = {"sample_dir": _rel(sample_dir)}
    for name in [
        "ledger.json",
        "raw_update.json",
        "normalized_event.json",
        "openemotion_result.json",
        "openemotion_trace.json",
        "response_plan.json",
        "outbox_record.json",
        "timeline.json",
        "tape.json",
        "replay.json",
        "summary.md",
        "sample.json",
    ]:
        path = sample_dir / name
        if path.exists():
            refs[name.replace(".json", "").replace(".md", "")] = _rel(path)
    return refs


def _derive_completeness(sample_dir: Path, ledger: Dict[str, Any]) -> Dict[str, bool]:
    completeness = dict((ledger.get("evidence_completeness") or {}))
    for name in [
        "raw_update",
        "normalized_event",
        "openemotion_result",
        "openemotion_trace",
        "response_plan",
        "outbox_record",
        "timeline",
        "tape",
        "replay",
    ]:
        completeness.setdefault(name, (sample_dir / f"{name}.json").exists())
    return completeness


def _is_oe_available(ledger: Dict[str, Any], completeness: Dict[str, bool]) -> bool:
    openemotion = ledger.get("openemotion") or {}
    result_payload = openemotion.get("result") or {}
    trace_payload = openemotion.get("trace_payload") or {}
    return bool(result_payload) or bool(trace_payload) or (
        completeness.get("openemotion_result", False) and completeness.get("openemotion_trace", False)
    )


def _classify_gap_types(
    completeness: Dict[str, bool],
    *,
    host_only: bool,
    replay_payload: Dict[str, Any],
    ledger_payload: Dict[str, Any],
) -> List[str]:
    gap_types: List[str] = []

    if host_only:
        gap_types.append("host_only_pre_runtime")

    if not completeness.get("raw_update", False):
        gap_types.append("raw_update_missing")

    if not completeness.get("normalized_event", False):
        gap_types.append("collector_timing_gap" if not host_only else "host_only_pre_runtime")

    if not completeness.get("openemotion_result", False):
        gap_types.append("collector_timing_gap" if not host_only else "host_only_pre_runtime")

    if not completeness.get("openemotion_trace", False):
        gap_types.append("collector_timing_gap" if not host_only else "host_only_pre_runtime")

    if not completeness.get("response_plan", False):
        gap_types.append("response_plan_missing")

    if not completeness.get("outbox_record", False):
        gap_types.append("send_record_missing")

    if not completeness.get("timeline", False) or not completeness.get("tape", False):
        gap_types.append("audit_artifact_missing")

    if not completeness.get("replay", False):
        gap_types.append("replay_missing")

    if replay_payload:
        if replay_payload.get("primary_ledger_ref") not in (None, "ledger.json"):
            gap_types.append("replay_mismatch")
        if replay_payload.get("sample_id") not in (None, ledger_payload.get("sample_id")):
            gap_types.append("replay_mismatch")
        if (
            replay_payload.get("replay_hash")
            and ledger_payload.get("replay_hash")
            and replay_payload.get("replay_hash") != ledger_payload.get("replay_hash")
        ):
            gap_types.append("replay_mismatch")

    deduped: List[str] = []
    for item in gap_types:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _build_run_record(sample_dir: Path) -> RunIndexRecord:
    ledger = _load_optional_json(sample_dir / "ledger.json") or {}
    ids = ledger.get("ids") or {}
    openemotion = ledger.get("openemotion") or {}
    host = ledger.get("host") or {}
    response_plan = host.get("response_plan") or {}
    trace_payload = openemotion.get("trace_payload") or {}
    cycle_delta = trace_payload.get("cycle_delta") or {}
    replay_payload = _load_optional_json(sample_dir / "replay.json") or {}

    completeness = _derive_completeness(sample_dir, ledger)
    oe_available = _is_oe_available(ledger, completeness)
    host_only = bool(response_plan) and not oe_available
    gap_types = _classify_gap_types(
        completeness,
        host_only=host_only,
        replay_payload=replay_payload,
        ledger_payload=ledger,
    )

    return RunIndexRecord(
        sample_id=ledger.get("sample_id") or sample_dir.name,
        timestamp=ledger.get("timestamp") or "",
        bundle_complete=all(completeness.values()) and not host_only,
        gap_types=gap_types,
        oe_available=oe_available,
        host_only=host_only,
        continuity_tags=[],
        repair_closure=bool(cycle_delta.get("repair_closure")),
        artifact_refs=_artifact_refs(sample_dir),
        response_plan_status=response_plan.get("status"),
        closure_family_id=cycle_delta.get("closure_family_id"),
        session_id=ids.get("session_id"),
        thread_id=ids.get("thread_id"),
        outcome_signature=cycle_delta.get("outcome_signature"),
        reflection_trigger=trace_payload.get("reflection_trigger"),
    )


def _build_growth_record(sample_dir: Path, run_record: RunIndexRecord) -> Optional[GrowthSignalRecord]:
    ledger = _load_optional_json(sample_dir / "ledger.json") or {}
    openemotion = ledger.get("openemotion") or {}
    result_payload = openemotion.get("result") or {}
    trace_payload = openemotion.get("trace_payload") or {}

    if not result_payload or not trace_payload:
        return None

    cycle_delta = trace_payload.get("cycle_delta") or {}
    reflection_note = result_payload.get("reflection_note") or {}
    return GrowthSignalRecord(
        sample_id=run_record.sample_id,
        timestamp=run_record.timestamp,
        memory_update_summary=result_payload.get("memory_update") or {},
        appraisal_delta_summary=result_payload.get("appraisal_state_delta") or {},
        reflection_summary={
            "trigger": reflection_note.get("trigger"),
            "promote_to_memory": reflection_note.get("promote_to_memory"),
            "diagnosis": reflection_note.get("diagnosis"),
            "proposed_adjustment": reflection_note.get("proposed_adjustment") or {},
        },
        response_tendency_summary=result_payload.get("response_tendency") or {},
        cycle_summary={
            "cycle_id": cycle_delta.get("cycle_id"),
            "closure_family_id": cycle_delta.get("closure_family_id"),
            "action_signature": cycle_delta.get("action_signature"),
            "outcome_signature": cycle_delta.get("outcome_signature"),
            "op": cycle_delta.get("op"),
            "repair_closure": cycle_delta.get("repair_closure"),
            "closure_consistency_score": cycle_delta.get("closure_consistency_score"),
            "reflection_trigger": trace_payload.get("reflection_trigger"),
        },
        session_id=run_record.session_id,
        thread_id=run_record.thread_id,
        closure_family_id=run_record.closure_family_id,
    )


def _failure_severity(cause_type: str) -> str:
    if cause_type in {"boundary_error", "authority_error", "e2e_broken"}:
        return "high"
    if cause_type in {"runtime_error", "schema_error"}:
        return "medium"
    return "low"


def _build_failure_records(failure_dir: Path = FAILURE_CASES_DIR) -> List[FailureIndexRecord]:
    if not failure_dir.exists():
        return []

    records: List[FailureIndexRecord] = []
    for path in sorted(failure_dir.glob("failure_*.json")):
        payload = _load_optional_json(path) or {}
        cause_type = payload.get("initial_cause_type") or "unknown"
        records.append(
            FailureIndexRecord(
                failure_id=payload.get("failure_id") or path.stem,
                timestamp=payload.get("timestamp") or "",
                cause_type=cause_type,
                severity=_failure_severity(cause_type),
                source="failure_case",
                artifact_ref=_rel(path),
                in_regression=bool(payload.get("in_regression")),
                retested_after_fix=bool(payload.get("retested_after_fix")),
                expected=payload.get("expected"),
                actual=payload.get("actual"),
            )
        )
    return records


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _section_sample_ids(text: str, heading_predicate) -> List[str]:
    sample_ids: List[str] = []
    current_heading = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("#").strip()
            continue
        if heading_predicate(current_heading):
            sample_ids.extend(SAMPLE_ID_RE.findall(stripped))
    deduped: List[str] = []
    for sample_id in sample_ids:
        if sample_id not in deduped:
            deduped.append(sample_id)
    return deduped


def _restart_external_refs(report_text: str) -> List[str]:
    refs: List[str] = []
    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "restart_egocore.sh --telegram" in stripped:
            refs.append(line.strip("- ").strip())
    return refs


def _build_continuity_records(observation_dir: Path = OBSERVATION_DIR) -> List[ContinuityObservationRecord]:
    sample_index_text = _read_text(observation_dir / "OBSERVATION_SAMPLE_INDEX.md")
    report_text = _read_text(observation_dir / "MVS_E5_OBSERVATION_REPORT.md")

    new_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "/new" in heading,
    )
    restart_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "restart continuity" in heading.lower(),
    )
    restore_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "restore continuity" in heading.lower(),
    )
    restart_refs = _restart_external_refs(report_text)

    return [
        ContinuityObservationRecord(
            scenario="new",
            status="direct_real" if new_sample_ids else "missing",
            sample_ids=new_sample_ids,
            external_evidence_refs=[],
            proof_summary="多次 `/new` 直接真实样本、完整 continuity probe、显式默认规则在 `/new` 后继续命中。",
            not_proved_summary="不证明 `restore continuity`、E5 稳定成立、Developmental Self 准入通过。",
            blocker="`/new` 已成立；当前 continuity 主 blocker 已切到 `restore` 与 evidence gap。",
        ),
        ContinuityObservationRecord(
            scenario="restart",
            status="cross_evidence" if restart_sample_ids else "missing",
            sample_ids=restart_sample_ids,
            external_evidence_refs=restart_refs,
            proof_summary="真实重启日志与 post-restart 命中样本已形成跨证据链正证据。",
            not_proved_summary="仍不等于 post-restart 命中样本已成为完整单样本 E4 bundle。",
            blocker="post-restart 命中样本仍非完整单样本 E4 bundle。",
        ),
        ContinuityObservationRecord(
            scenario="restore",
            status="direct_real" if restore_sample_ids else "missing",
            sample_ids=restore_sample_ids,
            external_evidence_refs=[],
            proof_summary=(
                "显式 restore 后，首条真实用户消息已形成完整 E4 bundle，随后 continuity probe 再次命中既有默认规则。"
                if restore_sample_ids
                else "当前没有直接真实 `restore` 样本。"
            ),
            not_proved_summary=(
                "不证明 E5 稳定成立，也不等于更长窗口下 continuity 已稳定。"
                if restore_sample_ids
                else "不能证明 `restore continuity` 已成立。"
            ),
            blocker=(
                "restore 首次正式补证已完成；当前更高优先级 blocker 已切到 post-restart 样本完整度与 evidence gap。"
                if restore_sample_ids
                else "`restore` 仍是 continuity 的最高优先级缺口。"
            ),
        ),
    ]


def _attach_continuity_tags(
    run_records: List[RunIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
) -> None:
    tag_map: Dict[str, List[str]] = defaultdict(list)
    for record in continuity_records:
        for sample_id in record.sample_ids:
            tag_map[sample_id].append(f"continuity:{record.scenario}")
    for run_record in run_records:
        run_record.continuity_tags = tag_map.get(run_record.sample_id, [])


def _build_gap_summary(
    run_records: List[RunIndexRecord],
    failure_records: List[FailureIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
) -> Dict[str, Any]:
    gap_counter: Counter[str] = Counter()
    incomplete_samples: List[str] = []
    for run_record in run_records:
        gap_counter.update(run_record.gap_types)
        if not run_record.bundle_complete:
            incomplete_samples.append(run_record.sample_id)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(run_records),
        "complete_runs": sum(1 for record in run_records if record.bundle_complete),
        "host_only_runs": sum(1 for record in run_records if record.host_only),
        "oe_available_runs": sum(1 for record in run_records if record.oe_available),
        "failure_case_count": len(failure_records),
        "gap_type_counts": dict(sorted(gap_counter.items())),
        "incomplete_sample_ids": incomplete_samples,
        "continuity_status": {record.scenario: record.status for record in continuity_records},
        "top_blockers": [
            "post_restart_sample_not_full_e4_bundle",
            "evidence_gap_still_present",
            "plasticity_reflection_still_weak",
        ],
    }


def _detect_plasticity_chains(growth_records: List[GrowthSignalRecord]) -> List[Dict[str, Any]]:
    by_family: Dict[str, List[GrowthSignalRecord]] = defaultdict(list)
    for record in growth_records:
        family_id = record.closure_family_id
        if family_id:
            by_family[family_id].append(record)

    chains: List[Dict[str, Any]] = []
    for family_id, records in by_family.items():
        ordered = sorted(records, key=lambda item: item.timestamp)
        for earlier, later in zip(ordered, ordered[1:]):
            earlier_outcome = earlier.cycle_summary.get("outcome_signature")
            later_outcome = later.cycle_summary.get("outcome_signature")
            if earlier_outcome in {"blocked", "failure"} and later_outcome == "success":
                if later.cycle_summary.get("repair_closure"):
                    chains.append(
                        {
                            "status": "partial_positive",
                            "sample_ids": [earlier.sample_id, later.sample_id],
                            "closure_family_id": family_id,
                            "proof_summary": "同一 closure family 从失败转为 success，且后者点亮 `repair_closure=true`。",
                            "not_proved_summary": "仍不足以单独证明跨更多回合的稳定 plasticity。",
                        }
                    )
                break
    return chains


def _detect_reflection_candidates(growth_records: List[GrowthSignalRecord]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    by_session: Dict[str, List[GrowthSignalRecord]] = defaultdict(list)
    for record in growth_records:
        if record.session_id:
            by_session[record.session_id].append(record)

    for record in sorted(growth_records, key=lambda item: item.timestamp):
        trigger = record.reflection_summary.get("trigger")
        if not trigger:
            continue
        downstream_effect = None
        for later in sorted(by_session.get(record.session_id or "", []), key=lambda item: item.timestamp):
            if later.timestamp <= record.timestamp:
                continue
            if later.response_tendency_summary != record.response_tendency_summary:
                downstream_effect = {
                    "sample_id": later.sample_id,
                    "response_tendency_summary": later.response_tendency_summary,
                }
                break
        candidates.append(
            {
                "status": "partial_positive" if downstream_effect else "partial_only",
                "sample_ids": [record.sample_id] + ([downstream_effect["sample_id"]] if downstream_effect else []),
                "trigger": trigger,
                "promote_to_memory": bool(record.reflection_summary.get("promote_to_memory")),
                "proof_summary": "存在结构化 `reflection_note`，并记录了 trigger / proposed_adjustment / promote_to_memory。",
                "not_proved_summary": (
                    "尚未看到干净、可重复的后续行为影响链。"
                    if not downstream_effect
                    else "已观察到后续 tendency 变化，但当前仍按 partial 处理。"
                ),
            }
        )
    return candidates


def _render_capture_status(
    run_records: List[RunIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
    gap_summary: Dict[str, Any],
) -> str:
    return f"""# REAL_MAINLINE_CAPTURE_STATUS

- 生成时间：`{gap_summary['generated_at']}`
- 真实样本总数：`{len(run_records)}`
- 完整单样本 E4 bundle：`{gap_summary['complete_runs']}`
- host-only 样本：`{gap_summary['host_only_runs']}`
- OE 结构化结果可用样本：`{gap_summary['oe_available_runs']}`

## Continuity

| scenario | status | sample_count | blocker |
|---|---|---:|---|
{chr(10).join(f"| {record.scenario} | {record.status} | {len(record.sample_ids)} | {record.blocker} |" for record in continuity_records)}

## 当前口径

- `/new continuity`：已作为直接真实正证据入账。
- `restart continuity`：已作为跨证据链正证据入账，但仍不是完整单样本 E4 bundle。
- `restore continuity`：已作为直接真实正证据入账。
- 本文件不能证明：`E5` 稳定成立、`Developmental Self` 准入通过。
"""


def _render_continuity_ledger(records: List[ContinuityObservationRecord]) -> str:
    blocks: List[str] = ["# CONTINUITY_OBSERVATION_LEDGER", ""]
    for record in records:
        blocks.append(f"## {record.scenario}")
        blocks.append(f"- status: `{record.status}`")
        blocks.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in record.sample_ids) if record.sample_ids else '无'}")
        blocks.append(
            f"- external_evidence_refs: {', '.join(f'`{ref}`' for ref in record.external_evidence_refs) if record.external_evidence_refs else '无'}"
        )
        blocks.append(f"- what_it_proves: {record.proof_summary}")
        blocks.append(f"- what_it_does_not_prove: {record.not_proved_summary}")
        blocks.append(f"- blocker: {record.blocker}")
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def _render_plasticity_reflection(
    plasticity_chains: List[Dict[str, Any]],
    reflection_candidates: List[Dict[str, Any]],
) -> str:
    lines = ["# PLASTICITY_REFLECTION_EVIDENCE", ""]
    lines.append("## Plasticity")
    if plasticity_chains:
        for item in plasticity_chains:
            lines.append(f"- status: `{item['status']}`")
            lines.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in item['sample_ids'])}")
            lines.append(f"- closure_family_id: `{item['closure_family_id']}`")
            lines.append(f"- proof: {item['proof_summary']}")
            lines.append(f"- not_proved: {item['not_proved_summary']}")
    else:
        lines.append("- 当前未发现满足“failure -> repair -> re-decision”或“repeated failure -> tendency change”的可归档链。")
    lines.append("")
    lines.append("## Reflection")
    if reflection_candidates:
        for item in reflection_candidates[:5]:
            lines.append(f"- status: `{item['status']}`")
            lines.append(f"- trigger: `{item['trigger']}`")
            lines.append(f"- promote_to_memory: `{item['promote_to_memory']}`")
            lines.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in item['sample_ids'])}")
            lines.append(f"- proof: {item['proof_summary']}")
            lines.append(f"- not_proved: {item['not_proved_summary']}")
    else:
        lines.append("- 当前未发现带结构化 `reflection_note` 的真实样本。")
    lines.append("")
    lines.append("## 结论限制")
    lines.append("- 本文件只证明当前可审计信号与候选链，不证明 plasticity 或 reflection 已稳定成立。")
    return "\n".join(lines).rstrip() + "\n"


def _render_gap_summary(gap_summary: Dict[str, Any]) -> str:
    return f"""# GAP_SUMMARY

- 生成时间：`{gap_summary['generated_at']}`
- 总样本：`{gap_summary['total_runs']}`
- 完整 bundle：`{gap_summary['complete_runs']}`
- host-only：`{gap_summary['host_only_runs']}`
- OE 可用：`{gap_summary['oe_available_runs']}`
- failure_cases：`{gap_summary['failure_case_count']}`

## Gap Types

| gap_type | count |
|---|---:|
{chr(10).join(f"| {name} | {count} |" for name, count in gap_summary['gap_type_counts'].items())}

## 当前 blocker

{chr(10).join(f"- `{item}`" for item in gap_summary['top_blockers'])}
"""


def _render_data_schema() -> str:
    return """# Dashboard Data Schema

所有 dashboard_v1 数据都来自只读派生索引，不是正式运行时状态源。

## files

- `runs.jsonl`: `RunIndexRecord`
- `continuity_observation.jsonl`: `ContinuityObservationRecord`
- `growth_signals.jsonl`: `GrowthSignalRecord`
- `failures.jsonl`: `FailureIndexRecord`
- `gap_summary.json`: gap 统计与 blocker 汇总
- `build_meta.json`: 索引生成元信息

## authority

- 主权威输入：`artifacts/telegram_real_mainline_v1/real_telegram/*/ledger.json`
- 兼容镜像：`sample.json` 只允许用于展示，不允许反向发明 OpenEmotion 语义
- continuity 观察口径：`artifacts/mvs_e5_observation/*.md`

## notes

- host-only 样本会进入 `runs.jsonl` 与 continuity 统计
- host-only 样本不会进入 `growth_signals.jsonl`
- `restore` 一旦拿到“显式 restore + 首条 post-restore 完整 bundle + continuity probe 命中”的真实链，就应升级为 `status=direct_real`
"""


def _render_readme() -> str:
    return """# Growth Dashboard v1

## 生成索引

```bash
python3 scripts/build_growth_dashboard_indexes.py
```

## 启动只读服务

```bash
cd EgoCore
PYTHONPATH=. python3 -m app.main --dashboard --host 127.0.0.1 --port 8787
```

## 页面

- `/runs`
- `/growth`
- `/failures`
- `/samples/<sample_id>`

## 说明

- Dashboard v1 只读，允许轮询刷新，不反写 EgoCore / OpenEmotion 状态
- 所有结论强度必须低于或等于当前 artifacts 与 observation 文档的证据强度
"""


def dashboard_source_last_modified(
    *,
    real_dir: Path = REAL_TELEGRAM_DIR,
    failure_dir: Path = FAILURE_CASES_DIR,
    observation_dir: Path = OBSERVATION_DIR,
    validation_doc: Path = VALIDATION_DOC,
) -> float:
    return _source_last_modified([real_dir, failure_dir, observation_dir, validation_doc])


def _source_last_modified(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
            continue
        for child in path.rglob("*"):
            if child.is_file():
                latest = max(latest, child.stat().st_mtime)
    return latest


def build_dashboard_indexes(
    *,
    real_dir: Path = REAL_TELEGRAM_DIR,
    failure_dir: Path = FAILURE_CASES_DIR,
    observation_dir: Path = OBSERVATION_DIR,
    output_dir: Path = DASHBOARD_DIR,
    validation_doc: Path = VALIDATION_DOC,
) -> DashboardBuildSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_dirs = _iter_sample_dirs(real_dir)
    run_records = [_build_run_record(sample_dir) for sample_dir in sample_dirs]
    continuity_records = _build_continuity_records(observation_dir=observation_dir)
    _attach_continuity_tags(run_records, continuity_records)
    growth_records = [
        record
        for sample_dir, run_record in zip(sample_dirs, run_records)
        for record in [_build_growth_record(sample_dir, run_record)]
        if record is not None
    ]
    failure_records = _build_failure_records(failure_dir=failure_dir)
    gap_summary = _build_gap_summary(run_records, failure_records, continuity_records)
    plasticity_chains = _detect_plasticity_chains(growth_records)
    reflection_candidates = _detect_reflection_candidates(growth_records)
    source_last_modified = dashboard_source_last_modified(
        real_dir=real_dir,
        failure_dir=failure_dir,
        observation_dir=observation_dir,
        validation_doc=validation_doc,
    )

    summary = DashboardBuildSummary(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_last_modified=source_last_modified,
        total_runs=len(run_records),
        complete_runs=gap_summary["complete_runs"],
        oe_available_runs=gap_summary["oe_available_runs"],
        host_only_runs=gap_summary["host_only_runs"],
        failure_cases=len(failure_records),
        continuity_status={record.scenario: record.status for record in continuity_records},
        gap_type_counts=gap_summary["gap_type_counts"],
        plasticity_chain_count=len(plasticity_chains),
        reflection_candidate_count=len(reflection_candidates),
    )

    _write_jsonl(output_dir / RUNS_FILE, (record.to_dict() for record in run_records))
    _write_jsonl(output_dir / CONTINUITY_FILE, (record.to_dict() for record in continuity_records))
    _write_jsonl(output_dir / GROWTH_FILE, (record.to_dict() for record in growth_records))
    _write_jsonl(output_dir / FAILURES_FILE, (record.to_dict() for record in failure_records))
    _write_json(output_dir / GAP_SUMMARY_FILE, gap_summary)
    _write_json(output_dir / BUILD_META_FILE, summary.to_dict())

    (output_dir / REAL_CAPTURE_STATUS_DOC).write_text(
        _render_capture_status(run_records, continuity_records, gap_summary),
        encoding="utf-8",
    )
    (output_dir / CONTINUITY_LEDGER_DOC).write_text(
        _render_continuity_ledger(continuity_records),
        encoding="utf-8",
    )
    (output_dir / PLASTICITY_REFLECTION_DOC).write_text(
        _render_plasticity_reflection(plasticity_chains, reflection_candidates),
        encoding="utf-8",
    )
    (output_dir / GAP_SUMMARY_DOC).write_text(
        _render_gap_summary(gap_summary),
        encoding="utf-8",
    )
    (output_dir / DATA_SCHEMA_DOC).write_text(_render_data_schema(), encoding="utf-8")
    (output_dir / README_DOC).write_text(_render_readme(), encoding="utf-8")

    return summary


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows
