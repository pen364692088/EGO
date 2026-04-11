#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "docs" / "codex" / "tasks" / "ai-self-awareness-minimal-framework"
INPUT_MANIFEST = TASK_ROOT / "MVS_REPLAY_CORPUS_MANIFEST.json"
OUTPUT_MANIFEST = TASK_ROOT / "CONTROLLED_REPLAY_CONVERSATION_MANIFEST.json"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_cases(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    episodes = list(manifest.get("episodes") or [])
    if episodes:
        cases: List[Dict[str, Any]] = []
        for episode in episodes:
            item = dict(episode)
            if "steps" not in item:
                step = dict(item.get("kernel_event") or {})
                item["steps"] = [step] if step else []
            item["case_id"] = str(item.get("case_id") or item.get("episode_id") or "").strip()
            item["family"] = str(item.get("family") or "").strip()
            cases.append(item)
        return cases

    cases = []
    for bucket in list(manifest.get("buckets") or []):
        family = str(bucket.get("bucket_id") or "").strip()
        for case in list(bucket.get("cases") or []):
            item = dict(case)
            item["case_id"] = str(item.get("case_id") or "").strip()
            item["family"] = family
            cases.append(item)
    return cases


def _convert_turn(step: Dict[str, Any], *, index: int) -> Dict[str, Any]:
    turn = {
        "turn_id": str(step.get("step_id") or f"turn_{index + 1:03d}"),
        "sequence": index,
        "session_id": str(step.get("session_id") or ""),
        "runtime_turn_id": str(step.get("turn_id") or f"turn_{index + 1:03d}"),
        "action_family": step.get("action_family"),
    }
    if step.get("kind") == "ingress":
        turn.update(
            {
                "kind": "user_message",
                "speaker": "user",
                "user_input": str(step.get("user_input") or ""),
                "current_goal": step.get("current_goal"),
            }
        )
    elif step.get("kind") == "tool_result":
        turn.update(
            {
                "kind": "external_result",
                "speaker": "system",
                "tool_result": dict(step.get("tool_result") or {}),
            }
        )
    else:
        raise ValueError(f"unsupported step kind: {step.get('kind')}")

    optional_fields = (
        "prediction_snapshot_prev",
        "task_summary_patch",
        "safety_context_patch",
        "executed_action_prev",
    )
    for field in optional_fields:
        if step.get(field) is not None:
            turn[field] = step[field]
    return turn


def build_manifest(source_manifest: Dict[str, Any]) -> Dict[str, Any]:
    source_contract = dict(source_manifest.get("runner_contract") or {})
    conversations = []
    for case in _iter_cases(source_manifest):
        slice_id = str(case.get("case_id") or "").strip()
        turns = [
            _convert_turn(dict(step), index=index)
            for index, step in enumerate(list(case.get("steps") or []))
        ]
        conversations.append(
            {
                "slice_id": slice_id,
                "family": str(case.get("family") or "").strip(),
                "source_type": "repo_authored_conversation_slice",
                "source_ref": f"CONTROLLED_REPLAY_CONVERSATION_MANIFEST.json#{slice_id}",
                "preloaded_state": dict(case.get("preloaded_state") or {}),
                "expected_scoring_surface": dict(case.get("expected_scoring_surface") or {}),
                "turns": turns,
                "has_external_result": any(turn.get("kind") == "external_result" for turn in turns),
            }
        )

    family_counts: Dict[str, int] = {}
    for item in conversations:
        family = str(item.get("family") or "")
        family_counts[family] = family_counts.get(family, 0) + 1

    return {
        "schema_version": "active_inference.controlled_replay_manifest.v1",
        "trial_id": "active_inference_controlled_replay",
        "split_id": "active_inference_controlled_replay_v1",
        "description": "Repo-authored conversation slices for the replay-validated active-inference winner under the frozen bounded contract.",
        "runner_contract": {
            "baseline_a_id": source_contract.get("baseline_a_id"),
            "baseline_b_id": source_contract.get("baseline_b_id"),
            "candidate_id": source_contract.get("challenger_id"),
            "ablation_ids": [],
            "supported_variant_ids": [
                source_contract.get("baseline_a_id"),
                source_contract.get("baseline_b_id"),
                source_contract.get("challenger_id"),
            ],
        },
        "source_policy": {
            "allowed_source_types": ["repo_authored_conversation_slice"],
            "banned_source_types": list((source_manifest.get("source_policy") or {}).get("banned_source_types") or []),
            "banned_source_ref_markers": list((source_manifest.get("source_policy") or {}).get("banned_source_ref_markers") or []),
        },
        "family_count": len(family_counts),
        "slice_count": len(conversations),
        "family_counts": family_counts,
        "conversations": conversations,
    }


def main() -> None:
    source = _load_json(INPUT_MANIFEST)
    manifest = build_manifest(source)
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT_MANIFEST}")


if __name__ == "__main__":
    main()
