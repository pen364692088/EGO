from typing import Dict, Any, List
from .artifact_skill_contract import ArtifactSkillRequest, ArtifactSkillResult
from .html_artifact_adapter import inspect_state, apply_edit


def _to_structured_observation(path: str, applied_edit: Dict[str, Any], state_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Skill v1 structured observation contract.

    Required fields:
    - target_path
    - applied_edit
    - current_state
    """
    inner_state = state_payload.get("state", {}) if isinstance(state_payload, dict) else {}
    return {
        "target_path": path,
        "applied_edit": applied_edit,
        "current_state": inner_state,
        # Backward compatibility for existing runtime fields
        "path": path,
        "state": inner_state,
        "kind": "html",
        "focus": applied_edit.get("scope") or "primary_text",
    }


def execute_html_skill(request: ArtifactSkillRequest, file_loader, file_writer) -> ArtifactSkillResult:
    targets = request.targets or []
    observations: List[Dict[str, Any]] = []
    completed_steps: List[str] = []
    failed_steps: List[str] = []

    if request.action == "create_artifact":
        for edit in request.edits:
            path = edit.target_path
            text_value = edit.value or "Hello, World!"
            content = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>{text_value}</title>\n</head>\n<body>\n  <h1>{text_value}</h1>\n</body>\n</html>\n"
            write_ok, write_err = file_writer(path, content)
            if not write_ok:
                failed_steps.append(f"create:{path}:{write_err}")
                continue
            state_payload = inspect_state(path, content)
            observations.append(_to_structured_observation(path, edit.to_dict(), state_payload))
            completed_steps.append(f"create:{path}")
        return ArtifactSkillResult(
            success=not failed_steps,
            action=request.action,
            artifact_type="html",
            targets=request.targets,
            observations=observations,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            summary="; ".join(completed_steps) if completed_steps else "; ".join(failed_steps),
        )

    if request.action == "inspect_artifact":
        for t in targets:
            path = t.get("path")
            ok, content_or_err = file_loader(path)
            if not ok:
                failed_steps.append(f"inspect:{path}:{content_or_err}")
                continue
            state_payload = inspect_state(path, content_or_err)
            observations.append(_to_structured_observation(path, {"operation": "inspect"}, state_payload))
            completed_steps.append(f"inspect:{path}")
        return ArtifactSkillResult(
            success=not failed_steps,
            action=request.action,
            artifact_type="html",
            targets=targets,
            observations=observations,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            summary="; ".join(completed_steps) if completed_steps else "; ".join(failed_steps),
        )

    if request.action in ("edit_artifact", "batch_edit_artifacts"):
        for edit in request.edits:
            path = edit.target_path
            ok, content_or_err = file_loader(path)
            if not ok:
                failed_steps.append(f"read:{path}:{content_or_err}")
                continue
            result = apply_edit(path, content_or_err, edit.scope or "primary_text", edit.property, edit.operation, edit.value)
            if result.get("content") == content_or_err:
                failed_steps.append(f"noop:{path}:{edit.property}:{edit.operation}")
                continue
            write_ok, write_err = file_writer(path, result["content"])
            if not write_ok:
                failed_steps.append(f"write:{path}:{write_err}")
                continue
            observations.append(_to_structured_observation(path, edit.to_dict(), result["state"]))
            completed_steps.append(f"edit:{path}:{edit.property}:{edit.operation}")
        return ArtifactSkillResult(
            success=not failed_steps,
            action=request.action,
            artifact_type="html",
            targets=targets,
            observations=observations,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            summary="; ".join(completed_steps) if completed_steps else "; ".join(failed_steps),
        )

    return ArtifactSkillResult(
        success=False,
        action=request.action,
        artifact_type="html",
        targets=targets,
        failed_steps=[f"unsupported_action:{request.action}"],
        summary=f"unsupported action: {request.action}",
    )
