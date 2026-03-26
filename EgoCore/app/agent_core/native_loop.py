from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import get_config, load_config
from app.llm_client import LLMClient, get_llm_client
from app.tools import execute_tool, get_registry, setup_tools

from .context_builder import NativeContextBuilder


@dataclass
class NativeLoopResult:
    reply_text: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    usage: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None


class NativeToolCallingLoop:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        context_builder: Optional[NativeContextBuilder] = None,
    ) -> None:
        self.llm_client = llm_client or get_llm_client(provider="qianfan", model="glm-5")
        self.context_builder = context_builder or NativeContextBuilder()
        self._ensure_tools_ready()

    def _ensure_tools_ready(self) -> None:
        try:
            cfg = get_config()
        except Exception:
            cfg = load_config(validate=False)
        registry = get_registry()
        if not registry.list_tools():
            setup_tools(cfg.tools if hasattr(cfg, "tools") else {})

    def _build_tool_definitions(self) -> List[Dict[str, Any]]:
        registry = get_registry()
        definitions: List[Dict[str, Any]] = []
        for name, info in registry.get_tools_info().items():
            if not info.get("enabled"):
                continue
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": info.get("description") or name,
                        "parameters": info.get("parameters_schema") or {"type": "object", "properties": {}},
                    },
                }
            )
        return definitions

    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        ingress_context: Optional[Dict[str, Any]] = None,
        proto_self_context: Optional[Dict[str, Any]] = None,
        max_rounds: int = 6,
    ) -> NativeLoopResult:
        messages = self.context_builder.build_messages(
            session_key=session_key,
            user_input=user_input,
            ingress_context=ingress_context,
            proto_self_context=proto_self_context,
        )
        tools = self._build_tool_definitions()
        tool_results: List[Dict[str, Any]] = []
        usage: List[Dict[str, Any]] = []
        last_finish_reason: Optional[str] = None

        for _ in range(max_rounds):
            response = await asyncio.to_thread(
                self.llm_client.chat_with_tools,
                messages,
                tools,
                temperature=0.1,
                max_tokens=4000,
                timeout=45,
            )
            last_finish_reason = response.finish_reason
            usage.append(response.usage or {})

            if response.has_tool_calls:
                assistant_message: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": call.get("id"),
                            "type": call.get("type", "function"),
                            "function": {
                                "name": call.get("name"),
                                "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                            },
                        }
                        for call in response.tool_calls
                    ],
                }
                messages.append(assistant_message)

                for call in response.tool_calls:
                    result = await asyncio.to_thread(
                        execute_tool,
                        call.get("name"),
                        call.get("arguments") or {},
                        None,
                        f"native_loop_{session_key}",
                    )
                    result_dict = result.to_dict()
                    tool_results.append(
                        {
                            "tool_name": call.get("name"),
                            "arguments": call.get("arguments") or {},
                            "result": result_dict,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "name": call.get("name"),
                            "content": json.dumps(result_dict, ensure_ascii=False),
                        }
                    )
                continue

            return NativeLoopResult(
                reply_text=response.content or "",
                tool_results=tool_results,
                usage=usage,
                finish_reason=last_finish_reason,
            )

        return NativeLoopResult(
            reply_text="",
            tool_results=tool_results,
            usage=usage,
            finish_reason=last_finish_reason or "max_rounds",
        )
