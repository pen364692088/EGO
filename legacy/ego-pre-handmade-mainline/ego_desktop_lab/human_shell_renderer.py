from __future__ import annotations

from typing import Any, Mapping, Sequence

from ego_desktop_lab.expression_layer import render_expression_from_decision_view


def render_human_shell_reply(
    view: Mapping[str, Any] | Any,
    *,
    provider_mode: str = "mock",
    reply_history: Sequence[str] = (),
) -> str:
    return render_expression_from_decision_view(
        view,
        provider_mode=provider_mode,
        reply_history=reply_history,
    ).rendered_text
