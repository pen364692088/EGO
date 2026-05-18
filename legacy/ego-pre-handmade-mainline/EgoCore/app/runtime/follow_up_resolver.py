from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class FollowUpEditIntent:
    intent: str
    target_path: Optional[str] = None
    target_scope: Optional[str] = None
    property_name: Optional[str] = None
    operation: Optional[str] = None
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "target_path": self.target_path,
            "target_scope": self.target_scope,
            "property": self.property_name,
            "operation": self.operation,
            "value": self.value,
        }


def resolve_follow_up(user_input: str, artifact_state: Dict[str, Any]) -> Optional[FollowUpEditIntent]:
    path = artifact_state.get("path")
    kind = artifact_state.get("kind")
    focus = artifact_state.get("active_focus") or artifact_state.get("default_edit_target")
    lowered = (user_input or "").lower().strip()

    if not path or kind != "html":
        return None

    if "你看一下" in user_input or "看一下" in user_input or "刚刚那个" in user_input:
        return FollowUpEditIntent(
            intent="inspect_artifact",
            target_path=path,
            target_scope=focus,
        )

    if "背景" in user_input and ("蓝" in user_input or "#0000ff" in lowered) and (("白色" in user_input or "改白" in user_input or "白" in user_input) and ("文字" in user_input or "字体" in user_input or "字" in user_input)):
        return FollowUpEditIntent(
            intent="edit_artifact_property",
            target_path=path,
            target_scope="combo",
            property_name="background_and_text_color",
            operation="set",
            value={"background_color": "#0000FF", "text_color": "#FFFFFF"},
        )

    if "背景" in user_input and ("蓝" in user_input or "#0000ff" in lowered):
        return FollowUpEditIntent(
            intent="edit_artifact_property",
            target_path=path,
            target_scope="body",
            property_name="background_color",
            operation="set",
            value="#0000FF",
        )

    if ("白色" in user_input or "改白" in user_input or "白" in user_input) and ("文字" in user_input or "字体" in user_input or "字" in user_input):
        return FollowUpEditIntent(
            intent="edit_artifact_property",
            target_path=path,
            target_scope=focus or "primary_text",
            property_name="text_color",
            operation="set",
            value="#FFFFFF",
        )

    if "字体" in user_input and ("大" in user_input or "放大" in user_input):
        scale = 3 if "3倍" in user_input or "三倍" in user_input else 1.5
        return FollowUpEditIntent(
            intent="edit_artifact_property",
            target_path=path,
            target_scope=focus or "primary_text",
            property_name="font_size",
            operation="scale",
            value=scale,
        )

    if any(x in user_input for x in ["再大一点", "再大些", "大一点", "大些"]):
        return FollowUpEditIntent(
            intent="edit_artifact_property",
            target_path=path,
            target_scope=focus or "primary_text",
            property_name="font_size",
            operation="scale",
            value=1.5,
        )

    return None
