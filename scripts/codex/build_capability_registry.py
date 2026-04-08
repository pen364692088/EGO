#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROGRAM_STATE = ROOT / "EgoCore" / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
ROOT_README = ROOT / "README.md"
EGOCORE_README = ROOT / "EgoCore" / "README.md"
OPENEMOTION_README = ROOT / "OpenEmotion" / "README.md"
LOGIC_FLOW = ROOT / "docs" / "CURRENT_PROJECT_LOGIC_FLOW.md"
DECISION_DOC = ROOT / "docs" / "PROTO_SELF_SINGLE_AUTHORITY_DECISION.md"
OUTPUT_MD = ROOT / "docs" / "CAPABILITY_REGISTRY.md"
OUTPUT_JSON = ROOT / "artifacts" / "capability_registry" / "CAPABILITY_REGISTRY_CURRENT.json"


@dataclass
class CapabilityRow:
    capability_name: str
    owner: str
    authority_source: str
    canonical_entry_file: str
    default_enabled: str
    current_evidence_level: str
    user_visible_symptom: str
    how_to_test: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_program_state() -> dict[str, Any]:
    return yaml.safe_load(PROGRAM_STATE.read_text(encoding="utf-8")) or {}


def _load_supporting_text() -> dict[str, str]:
    return {
        "root_readme": ROOT_README.read_text(encoding="utf-8"),
        "egocore_readme": EGOCORE_README.read_text(encoding="utf-8"),
        "openemotion_readme": OPENEMOTION_README.read_text(encoding="utf-8"),
        "logic_flow": LOGIC_FLOW.read_text(encoding="utf-8"),
        "single_authority_decision": DECISION_DOC.read_text(encoding="utf-8"),
    }


def build_registry_rows() -> list[CapabilityRow]:
    program_state = _load_program_state()
    _ = _load_supporting_text()
    mvp13 = _read_json(ROOT / "OpenEmotion" / "artifacts" / "mvp13" / "MVP13_COMPLETION_CURRENT.json")
    mvp14 = _read_json(ROOT / "OpenEmotion" / "artifacts" / "mvp14" / "MVP14_COMPLETION_CURRENT.json")
    mvp15 = _read_json(ROOT / "OpenEmotion" / "artifacts" / "mvp15" / "MVP15_COMPLETION_CURRENT.json")
    mvp16 = _read_json(ROOT / "OpenEmotion" / "artifacts" / "mvp16" / "MVP16_COMPLETION_CURRENT.json")
    mvp12 = _read_json(ROOT / "OpenEmotion" / "artifacts" / "mvp12" / "MVP12_COMPLETION_CURRENT.json")
    subject_audit = _read_json(ROOT / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1" / "SUBJECT_MAINLINE_AUDIT_CURRENT.json")
    provider_gate = _read_json(ROOT / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1" / "PROVIDER_RUNTIME_OPENEMOTION_E2E_GATE_CURRENT.json")

    subject_axis = ((program_state.get("axes") or {}).get("subject_axis") or {})
    host_runtime = program_state.get("host_runtime_contract") or {}

    def evidence_line(text: str) -> str:
        return text

    rows = [
        CapabilityRow(
            capability_name="Telegram 正式主链",
            owner="EgoCore",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/telegram_bot.py",
            default_enabled="yes",
            current_evidence_level=evidence_line(f"{host_runtime.get('evidence_state', 'unknown')} + repo-level current README"),
            user_visible_symptom="Telegram 对话、任务执行与 delivery 走统一宿主主链。",
            how_to_test="第 0 链 `python3 scripts/codex/run_acceptance_subject_ingress_mainline.py` + `EXP-SUBJECT-INGRESS`",
        ),
        CapabilityRow(
            capability_name="proto_self_v2 主体链",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level=evidence_line(
                f"{subject_axis.get('current_state', 'unknown')} + formal surface on Telegram natural-language mainline"
            ),
            user_visible_symptom="真实样本 `/flow` 中出现 `Subject Understanding`、`proto_self.trace.v2`、多轴上下文载荷；当前 formal surface 是 `proto_self_v2`。",
            how_to_test="第 0 链 + `EXP-FLOW-CANONICAL-FIELDS`",
        ),
        CapabilityRow(
            capability_name="identity invariants authority surface",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="OpenEmotion/openemotion/proto_self/state.py",
            default_enabled="yes",
            current_evidence_level="formal mainline currently executes v1 substrate; identity formal owner not wired",
            user_visible_symptom="当前 identity runtime authority 仍由 `proto_self` v1 substrate 提供，而不是 `openemotion.identity` formal owner。",
            how_to_test="读 `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` + `docs/PROTO_SELF_MVP_AUTHORITY_AUDIT.md`",
        ),
        CapabilityRow(
            capability_name="self-model authority surface",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="formal owner active; v1 substrate remains active compute/proposal-only layer",
            user_visible_symptom="`self_model` formal owner 已接入 governed writeback，但 base delta 仍由 v1 substrate 参与计算。",
            how_to_test="`python3 scripts/codex/run_acceptance_self_model_causality.py` + `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`",
        ),
        CapabilityRow(
            capability_name="drives / appraisal authority surface",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="formal owner active; v1 drive substrate remains active compute/proposal-only layer",
            user_visible_symptom="`endogenous_drives` formal owner 已接入 governed writeback，但 base drive/appraisal 仍由 v1 substrate 参与计算。",
            how_to_test="`python3 scripts/codex/run_acceptance_drives_causality.py` + `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`",
        ),
        CapabilityRow(
            capability_name="reflection / structured revision authority surface",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="formal owner active; v1 reflection note remains transient trigger-only layer",
            user_visible_symptom="`reflective_self` formal owner 已接入 governed writeback，但 v1 `reflection_note` 仍是 active trigger layer，不再是 authority。",
            how_to_test="`python3 scripts/codex/run_acceptance_reflection_boundary.py` + `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md`",
        ),
        CapabilityRow(
            capability_name="Mandatory Subject Ingress",
            owner="EgoCore",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/openemotion_hooks/subject_gate.py",
            default_enabled="partial",
            current_evidence_level=evidence_line(subject_audit.get("current_verdict", {}).get("headline", "current audit required")),
            user_visible_symptom="已授权 turn 应先进入主体再由宿主裁决；host-only bypass 会在第 0 链里暴露。",
            how_to_test="第 0 链 `python3 scripts/codex/run_acceptance_subject_ingress_mainline.py` + `EXP-SUBJECT-INGRESS`",
        ),
        CapabilityRow(
            capability_name="same-session continuity",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="real Telegram E5 same-session continuity (README current state)",
            user_visible_symptom="同一 session 内能记住刚刚的话题、对象和刚完成结果。",
            how_to_test="`python3 scripts/codex/run_acceptance_continuity.py` + `EXP-CONTINUITY-SAME-SESSION`",
        ),
        CapabilityRow(
            capability_name="cross-session continuity",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="same-day cross-session continuity `2 / 2` (README current state)",
            user_visible_symptom="新 `/new` 后仍能在当日跨 session 恢复持续身份与上下文线索。",
            how_to_test="`python3 scripts/codex/run_acceptance_continuity.py` + `EXP-CONTINUITY-CROSS-SESSION`",
        ),
        CapabilityRow(
            capability_name="cross-day continuity",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="partial",
            current_evidence_level="cross-day continuity `1 / 2`, later-day sample pending (current README conservative line)",
            user_visible_symptom="跨天后仍保持同一主体的线索，但当前证据仍不满配。",
            how_to_test="`python3 scripts/codex/run_acceptance_continuity.py` + `EXP-CONTINUITY-CROSS-DAY`",
        ),
        CapabilityRow(
            capability_name="self-model projection",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proto_self_runtime.py",
            default_enabled="yes",
            current_evidence_level="live self-model projection enabled with auto-bootstrap (README + flow current behavior)",
            user_visible_symptom="`/flow` 里 `contexts_seen.self_model=true`，且 `self_model_context_source=loaded|bootstrapped_live`。",
            how_to_test="`python3 scripts/codex/run_acceptance_self_model_causality.py` + `EXP-SELF-MODEL-PROJECTION`",
        ),
        CapabilityRow(
            capability_name="self-model causal influence",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="OpenEmotion/openemotion/proto_self_v2/kernel.py",
            default_enabled="yes",
            current_evidence_level=f"{mvp13.get('status', 'unknown')} / controlled axis only",
            user_visible_symptom="在受控 proof 中，只改 self-model 条件会改变 downstream choice/tendency。",
            how_to_test="`python3 scripts/codex/run_acceptance_self_model_causality.py` + `EXP-SELF-MODEL-CAUSALITY`",
        ),
        CapabilityRow(
            capability_name="drives causal influence",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="OpenEmotion/openemotion/proto_self_v2/endogenous_drive_context.py",
            default_enabled="yes",
            current_evidence_level=f"{mvp14.get('status', 'unknown')} / controlled axis only",
            user_visible_symptom="verification / conservation / repair pressure 会改变 candidate bias 与 maintenance bias。",
            how_to_test="`python3 scripts/codex/run_acceptance_drives_causality.py` + `EXP-DRIVES-CAUSALITY`",
        ),
        CapabilityRow(
            capability_name="reflection writeback + proposal-only boundary",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="OpenEmotion/openemotion/proto_self_v2/reflection.py",
            default_enabled="yes",
            current_evidence_level=f"{mvp15.get('status', 'unknown')} / proposal_only discipline preserved",
            user_visible_symptom="会出现 reflection writeback candidate，但不会突破 `behavioral_authority = none`。",
            how_to_test="`python3 scripts/codex/run_acceptance_reflection_boundary.py` + `EXP-REFLECTION-BOUNDARY`",
        ),
        CapabilityRow(
            capability_name="developmental continuity",
            owner="OpenEmotion",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="OpenEmotion/openemotion/proto_self_v2/developmental.py",
            default_enabled="yes",
            current_evidence_level=f"{mvp16.get('status', 'unknown')} / controlled axis only",
            user_visible_symptom="growth / stagnation / identity guard 会改变 developmental bias 与 suggested next step。",
            how_to_test="`python3 scripts/codex/run_acceptance_developmental_proactive.py` + `EXP-DEVELOPMENTAL-CONTINUITY`",
        ),
        CapabilityRow(
            capability_name="proactive bounded expression",
            owner="EgoCore",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/runtime_v2/proactive_telegram_cycle.py",
            default_enabled="feature_flag_off / allowlist_only",
            current_evidence_level=f"{mvp12.get('status', 'unknown')} + host-governed proactive cycle current artifact",
            user_visible_symptom="满足 host-governed 条件时才允许 bounded proactive follow-up / outbox / delivery。",
            how_to_test="`python3 scripts/codex/run_acceptance_developmental_proactive.py` + `EXP-PROACTIVE-BOUNDED`",
        ),
        CapabilityRow(
            capability_name="/flow explanation layer",
            owner="EgoCore",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="EgoCore/app/dashboard/server.py",
            default_enabled="yes",
            current_evidence_level="dashboard read-only explanation layer with canonical fields",
            user_visible_symptom="一屏内看到 Input -> Host -> Subject -> Host -> Output 与关键 bounded fields。",
            how_to_test="打开 `/flow` + `EXP-FLOW-CANONICAL-FIELDS`",
        ),
        CapabilityRow(
            capability_name="provider/runtime E2E gate",
            owner="EgoCore",
            authority_source="program_state_unified + current_readme_logic_flow supplement",
            canonical_entry_file="scripts/codex/run_provider_runtime_openemotion_e2e_gate.py",
            default_enabled="yes",
            current_evidence_level=evidence_line(
                "all_passed=true admission gate current report"
                if provider_gate.get("all_passed") is True
                else "provider/runtime gate currently not all-passed"
            ),
            user_visible_symptom="provider/runtime 改动后必须通到 OpenEmotion evidence，不能只做局部 smoke。",
            how_to_test="`python3 scripts/codex/run_provider_runtime_openemotion_e2e_gate.py --session-key <telegram:...>` + `EXP-PROVIDER-RUNTIME-GATE`",
        ),
    ]
    return rows


def render_markdown(rows: list[CapabilityRow]) -> str:
    lines = [
        "# Capability Registry",
        "",
        "> 这是人类索引与派生层，不是新的 authority source。当前主权威仍是 `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`，并由当前 README / logic flow 补充尚未回写到 YAML 的现状；`docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` 只作为 prescriptive supplement，不升格为 authority source。",
        "",
        "生成方式：`python3 scripts/codex/build_capability_registry.py`",
        "",
        "| capability_name | owner | authority_source | canonical_entry_file | default_enabled | current_evidence_level | user_visible_symptom | how_to_test |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        payload = asdict(row)
        cells = [str(payload[key]).replace("\n", " ").replace("|", "\\|") for key in payload]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def build_registry_payload() -> dict[str, Any]:
    rows = build_registry_rows()
    return {
        "generated_from": [
            str(PROGRAM_STATE.relative_to(ROOT)),
            str(ROOT_README.relative_to(ROOT)),
            str(EGOCORE_README.relative_to(ROOT)),
            str(OPENEMOTION_README.relative_to(ROOT)),
            str(LOGIC_FLOW.relative_to(ROOT)),
            str(DECISION_DOC.relative_to(ROOT)),
        ],
        "rows": [asdict(row) for row in rows],
    }


def main() -> int:
    payload = build_registry_payload()
    markdown = render_markdown([CapabilityRow(**row) for row in payload["rows"]])
    OUTPUT_MD.write_text(markdown, encoding="utf-8")
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
