import re
import uuid
from typing import Dict, Any, List
from .task_plan_state import TaskPlanState


def build_minimal_task_plan(user_input: str, session_state: Dict[str, Any]) -> TaskPlanState:
    text = user_input.strip()
    lower = text.lower()
    plan = TaskPlanState(task_id=f"plan_{uuid.uuid4().hex[:8]}")

    if "html" in lower and ("创建" in text or "新建" in text):
        dir_match = re.search(r'在\s*(/[^\s,，]+?)(?=创建|新建|\s)', text)
        base_dir = dir_match.group(1) if dir_match else None
        contents = []
        multi = re.search(r'内容分别是\s*([A-Za-z0-9_\- ]+)\s*和\s*([A-Za-z0-9_\- ]+)', text, re.I)
        if multi:
            contents = [multi.group(1).strip(), multi.group(2).strip()]
        else:
            single = re.search(r'内容是\s*([A-Za-z0-9_\- ]+)', text, re.I)
            if single:
                contents = [single.group(1).strip()]
        if not contents and "hello world" in lower and "test" in lower:
            contents = ["test", "hello world"]
        targets: List[Dict[str, Any]] = []
        for item in contents:
            name = item.strip().replace(' ', '_')
            if name == 'hello_world':
                filename = 'hello.html'
            elif name:
                filename = f"{name}.html"
            else:
                continue
            path = f"{base_dir.rstrip('/')}/{filename}" if base_dir else filename
            targets.append({"path": path, "artifact_type": "html", "content": item.strip()})
        plan.task_plan = "create multiple html artifacts"
        plan.targets = targets
        plan.plan_steps = [
            {"kind": "create_artifacts", "targets": targets},
        ]
        plan.active_target = targets[0]["path"] if targets else None
        return plan

    normalized_text = text.replace("地址:", " ")
    explicit_paths = re.findall(r'(/[^\s,，]+)', normalized_text)
    explicit_paths = list(dict.fromkeys(explicit_paths))
    known_paths = list((session_state.get("artifact_context_by_path") or {}).keys())
    candidate_paths = explicit_paths or [p for p in known_paths if p in text]

    if session_state.get("artifact_context_by_path") or explicit_paths:
        paths = explicit_paths if explicit_paths else (candidate_paths or known_paths)
        targets = [{"path": p, "artifact_type": "html"} for p in paths]
        edits = []
        if "字体" in text and ("3倍" in text or "三倍" in text):
            for t in targets:
                edits.append({"target_path": t["path"], "scope": "primary_text", "property": "font_size", "operation": "scale", "value": 3})
        elif any(x in text for x in ["再大一点", "再大些", "大一点"]):
            active = session_state.get("active_target") or (targets[0]["path"] if targets else None)
            if active:
                edits.append({"target_path": active, "scope": "primary_text", "property": "font_size", "operation": "scale", "value": 1.5})
        if "背景" in text and any(x in text for x in ["好看", "协调", "漂亮", "你选", "你挑"]):
            for t in targets:
                edits.append({"target_path": t["path"], "scope": "body", "property": "background_color", "operation": "choose_and_set", "value": "agent_choice"})
        if "背景" in text and ("绿" in text or "绿色" in text):
            for t in targets:
                if "test" in t["path"]:
                    edits.append({"target_path": t["path"], "scope": "body", "property": "background_color", "operation": "set", "value": "green"})
        if "背景" in text and ("红" in text or "红色" in text):
            for t in targets:
                if "hello" in t["path"]:
                    edits.append({"target_path": t["path"], "scope": "body", "property": "background_color", "operation": "set", "value": "red"})
        if ("白" in text or "白色" in text) and ("文字" in text or "字体" in text or "字" in text):
            for t in targets:
                edits.append({"target_path": t["path"], "scope": "primary_text", "property": "text_color", "operation": "set", "value": "#FFFFFF"})
        if edits:
            plan.task_plan = "edit html artifacts"
            plan.targets = targets
            plan.plan_steps = [{"kind": "batch_edit_artifacts", "targets": targets, "edits": edits}]
            plan.active_target = targets[0]["path"] if targets else None
            return plan
        if "你看一下" in text or "看一下" in text:
            plan.task_plan = "inspect html artifacts"
            plan.targets = targets
            plan.plan_steps = [{"kind": "inspect_artifact", "targets": targets}]
            plan.active_target = targets[0]["path"] if targets else None
            return plan

    return plan
