from __future__ import annotations

import asyncio
import json
from typing import Dict, List

from app.llm_client import get_llm_client

from .action_protocol import RUNTIME_V2_SYSTEM_PROMPT, RuntimeV2Action
from .prompt_files import RuntimeV2PromptFiles
from .state import RuntimeV2State


class RuntimeV2DecisionEngine:
    def __init__(self) -> None:
        self.prompt_files = RuntimeV2PromptFiles()
        self.llm_client = None

    def build_system_prompt(self) -> str:
        bundle = self.prompt_files.load()
        rendered = bundle.render()
        if rendered:
            return rendered + "\n\n## BUILTIN_RUNTIME_V2_CONTRACT\n" + RUNTIME_V2_SYSTEM_PROMPT
        return RUNTIME_V2_SYSTEM_PROMPT

    def build_policy_hint_context(self, proto_self_context: dict) -> str:
        """
        从 Proto-Self Kernel 输出构建 policy hint 注入文本。
        """
        if not proto_self_context:
            return ""
        
        policy_hint = proto_self_context.get("policy_hint", {})
        response_tendency = proto_self_context.get("response_tendency", {})
        reflection_note = proto_self_context.get("reflection_note")
        
        parts = []
        
        if policy_hint:
            risk_bias = policy_hint.get("risk_bias", "normal")
            closure_bias = policy_hint.get("closure_bias", False)
            ask_preferred = policy_hint.get("ask_preferred", False)
            
            if risk_bias == "high":
                parts.append("- 当前风险评估偏高，谨慎行事")
            if closure_bias:
                parts.append("- 有未完成任务，优先收尾")
            if ask_preferred:
                parts.append("- 建议在执行前向用户确认")
        
        if response_tendency:
            preferred_mode = response_tendency.get("preferred_mode", "respond")
            preferred_tone = response_tendency.get("preferred_tone", "calm")
            if preferred_mode == "repair":
                parts.append("- 系统处于修复模式，注意错误恢复")
            if preferred_tone == "cautious":
                parts.append("- 回复基调：谨慎")
        
        if reflection_note:
            trigger = reflection_note.get("trigger", "")
            if trigger == "external_failure":
                parts.append("- 刚才的操作失败，考虑重试或换方案")
            elif trigger == "identity_conflict":
                parts.append("- 检测到身份边界冲突，注意审查")
        
        if not parts:
            return ""
        
        return "\n## 主体倾向提示\n" + "\n".join(parts) + "\n"

    async def decide(self, state: RuntimeV2State) -> RuntimeV2Action:
        system_prompt = self.build_system_prompt()
        
        # 注入 Proto-Self Kernel policy hint
        policy_hint_context = self.build_policy_hint_context(state.proto_self_context or {})
        if policy_hint_context:
            system_prompt = system_prompt + policy_hint_context
        
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "state": state.to_prompt_context(),
                        "instruction": "根据当前状态输出下一个 JSON action。若需要执行，优先 act；若执行后可验证完成，则 complete；若只是寒暄，chat。",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]
        try:
            if self.llm_client is None:
                self.llm_client = get_llm_client(provider="qianfan", model="glm-5")
            response = await asyncio.to_thread(
                self.llm_client.generate_with_messages,
                messages,
                temperature=0.1,
                max_tokens=500,
                timeout=30,
            )
            # Record token usage if available
            if response.usage:
                prompt_tokens = response.usage.get("prompt_tokens", 0) or response.usage.get("input_tokens", 0)
                completion_tokens = response.usage.get("completion_tokens", 0) or response.usage.get("output_tokens", 0)
                state.record_token_usage(prompt_tokens, completion_tokens)
            return RuntimeV2Action.from_model_output(response.content)
        except Exception as e:
            return RuntimeV2Action(
                type="ask",
                question=f"Runtime v2 当前模型决策不可用：{e}",
                raw={"type": "ask", "error": str(e)},
            )
