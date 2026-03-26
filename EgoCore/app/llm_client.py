"""
OpenEmotion Agent Runtime - LLM Client

Unified LLM client supporting multiple providers.
Configuration-driven model selection.
"""

import json
import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import httpx

from app.config import get_config

# Anthropic SDK
import anthropic


@dataclass
class LLMResponse:
    """LLM response model."""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class BaseLLMClient(ABC):
    """Base class for LLM clients."""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass
    
    @abstractmethod
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response from message list."""
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Generate response with native tool-calling support."""
        pass


def _normalize_tool_call_arguments(arguments: Any) -> Dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"raw": arguments}
    return {}


def _extract_openai_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        out.append(
            {
                "id": call.get("id"),
                "type": call.get("type", "function"),
                "name": function.get("name"),
                "arguments": _normalize_tool_call_arguments(function.get("arguments")),
            }
        )
    return out


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using chat completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.generate_with_messages(messages, **kwargs)
    
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response from message list."""
        url = f"{self.BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        
        # Add optional parameters
        if "top_p" in self.config:
            data["top_p"] = self.config["top_p"]
        if "frequency_penalty" in self.config:
            data["frequency_penalty"] = self.config["frequency_penalty"]
        if "presence_penalty" in self.config:
            data["presence_penalty"] = self.config["presence_penalty"]
        
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        
        choice = result["choices"][0]
        message = choice.get("message", {})
        
        return LLMResponse(
            content=message.get("content") or "",
            model=result["model"],
            provider="openai",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.get("tool_choice", "auto"),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.2)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        choice = result["choices"][0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            model=result.get("model", self.model),
            provider="openai",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )


class AnthropicClient(BaseLLMClient):
    """Anthropic API client."""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using messages API."""
        url = f"{self.BASE_URL}/messages"
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            data["system"] = system_prompt
        
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        
        content = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        
        return LLMResponse(
            content=content,
            model=result["model"],
            provider="anthropic",
            usage={
                "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                "output_tokens": result.get("usage", {}).get("output_tokens", 0)
            },
            finish_reason=result.get("stop_reason"),
            raw_response=result
        )
    
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response from message list."""
        # Anthropic uses different message format
        # Convert and call generate
        system_prompt = None
        converted_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                converted_messages.append(msg)
        
        # For simplicity, concatenate messages
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in converted_messages])
        return self.generate(prompt, system_prompt=system_prompt, **kwargs)

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        raise NotImplementedError("Anthropic native tool calling is not wired in EgoCore yet")


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API client (OpenAI-compatible)."""
    
    BASE_URL = "https://api.deepseek.com/v1"
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate using OpenAI-compatible API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.generate_with_messages(messages, **kwargs)
    
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response from message list."""
        url = f"{self.BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        
        choice = result["choices"][0]
        message = choice.get("message", {})
        
        return LLMResponse(
            content=message.get("content") or "",
            model=result["model"],
            provider="deepseek",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.get("tool_choice", "auto"),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.2)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        choice = result["choices"][0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            model=result.get("model", self.model),
            provider="deepseek",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )


class QianfanClient(BaseLLMClient):
    """Baidu Qianfan Coding API client."""
    
    # 百度千帆 Coding Plan API endpoint
    BASE_URL = "https://qianfan.baidubce.com/v2/coding"
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate using OpenAI-compatible API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.generate_with_messages(messages, **kwargs)
    
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate response from message list."""
        url = f"{self.BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        
        choice = result["choices"][0]
        message = choice.get("message", {})
        
        return LLMResponse(
            content=message.get("content") or "",
            model=result.get("model", self.model),
            provider="qianfan",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.get("tool_choice", "auto"),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.2)),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
        }
        with httpx.Client(timeout=kwargs.get("timeout", 60)) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
        choice = result["choices"][0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            model=result.get("model", self.model),
            provider="qianfan",
            usage=result.get("usage"),
            finish_reason=choice.get("finish_reason"),
            raw_response=result,
            tool_calls=_extract_openai_tool_calls(message),
        )


class LLMClient:
    """
    Unified LLM client.
    
    Supports multiple providers:
    - Baidu Qianfan (default)
    - OpenAI
    - Anthropic
    - DeepSeek
    
    Configuration-driven via llm.yaml.
    """
    
    PROVIDERS = {
        "qianfan": QianfanClient,
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "deepseek": DeepSeekClient,
    }
    
    ENV_KEY_MAP = {
        "qianfan": "QIANFAN_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM client.
        
        Args:
            provider: Provider name (default from config)
            model: Model name (default from config)
        """
        config = get_config()
        
        self.provider = provider or config.llm.get("default_provider", "openai")
        self.model = model or config.llm.get("default_model", "gpt-4o-mini")
        
        # Get API key
        env_key = self.ENV_KEY_MAP.get(self.provider)
        if not env_key:
            raise ValueError(f"Unknown provider: {self.provider}")
        
        self.api_key = config.get_env(env_key)
        if not self.api_key:
            raise ValueError(f"API key not set: {env_key}")
        
        # Get model config
        models = config.llm.get("models", {})
        model_config = models.get(self.model, {})
        
        # Create client
        client_class = self.PROVIDERS.get(self.provider)
        if not client_class:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        self.client = client_class(
            api_key=self.api_key,
            model=self.model,
            **model_config
        )
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
        
        Returns:
            LLMResponse
        """
        return self.client.generate(prompt, system_prompt=system_prompt, **kwargs)
    
    def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from message list.
        
        Args:
            messages: List of message dicts
            **kwargs: Additional parameters
        
        Returns:
            LLMResponse
        """
        return self.client.generate_with_messages(messages, **kwargs)

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        return self.client.chat_with_tools(messages, tools, **kwargs)
    
    def get_prompt(self, prompt_name: str) -> str:
        """
        Get a prompt template from config.
        
        Args:
            prompt_name: Name of the prompt
        
        Returns:
            Prompt template string
        """
        config = get_config()
        return config.get_prompt(prompt_name)


# Global LLM client instance
_llm_client: Optional[LLMClient] = None
_llm_client_overrides: Dict[tuple[Optional[str], Optional[str]], LLMClient] = {}


def get_llm_client(provider: Optional[str] = None, model: Optional[str] = None) -> LLMClient:
    """
    Get LLM client instance.
    
    Args:
        provider: Provider override
        model: Model override
    
    Returns:
        LLMClient instance
    """
    global _llm_client
    
    if provider or model:
        key = (provider, model)
        cached = _llm_client_overrides.get(key)
        if cached is None:
            cached = LLMClient(provider=provider, model=model)
            _llm_client_overrides[key] = cached
        return cached
    
    if _llm_client is None:
        _llm_client = LLMClient()
    
    return _llm_client
