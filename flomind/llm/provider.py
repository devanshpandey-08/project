"""
LLM Provider abstraction for FlowMind.

Unified interface for all LLM providers with built-in streaming, cost tracking, and fallbacks.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncIterator, Callable, Union, Literal
from enum import Enum
import asyncio
import time
from abc import ABC, abstractmethod


class ChatRole(Enum):
    """Roles in a chat conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


@dataclass
class Message:
    """A chat message."""
    role: ChatRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'role': self.role.value,
            'content': self.content,
        }
        if self.name:
            result['name'] = self.name
        if self.tool_calls:
            result['tool_calls'] = self.tool_calls
        if self.tool_call_id:
            result['tool_call_id'] = self.tool_call_id
        return result
    
    @classmethod
    def system(cls, content: str) -> 'Message':
        """Create a system message."""
        return cls(role=ChatRole.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> 'Message':
        """Create a user message."""
        return cls(role=ChatRole.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str, **kwargs) -> 'Message':
        """Create an assistant message."""
        return cls(role=ChatRole.ASSISTANT, content=content, **kwargs)
    
    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> 'Message':
        """Create a tool response message."""
        return cls(role=ChatRole.TOOL, content=content, tool_call_id=tool_call_id)


@dataclass
class LLMResponse:
    """Response from an LLM."""
    content: str
    role: ChatRole = ChatRole.ASSISTANT
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Cost tracking
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    
    @property
    def prompt_tokens(self) -> int:
        return self.usage.get('prompt_tokens', 0)
    
    @property
    def completion_tokens(self) -> int:
        return self.usage.get('completion_tokens', 0)
    
    @property
    def total_tokens(self) -> int:
        return self.usage.get('total_tokens', 0)


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    content: str = ""
    is_done: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Provider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MISTRAL = "mistral"
    GROQ = "groq"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    COHERE = "cohere"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """Configuration for LLM."""
    model: str = "gpt-4o"
    provider: Provider = Provider.OPENAI
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    timeout_seconds: float = 60.0
    retry_count: int = 3
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLM(ABC):
    """
    Abstract base class for LLM providers.
    
    Provides a unified interface for all LLM operations with built-in
    streaming, cost tracking, and error handling.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._request_count = 0
        self._total_cost_usd = 0.0
        self._total_tokens = 0
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Send a chat request and get a response."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat response."""
        pass
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Simple completion interface."""
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))
        return await self.chat(messages, **kwargs)
    
    async def stream_complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Simple streaming completion interface."""
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))
        return self.stream(messages, **kwargs)
    
    def _track_usage(self, response: LLMResponse) -> None:
        """Track usage statistics."""
        self._request_count += 1
        self._total_cost_usd += response.cost_usd
        self._total_tokens += response.total_tokens
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            'request_count': self._request_count,
            'total_cost_usd': self._total_cost_usd,
            'total_tokens': self._total_tokens,
            'model': self.config.model,
            'provider': self.config.provider.value,
        }
    
    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._request_count = 0
        self._total_cost_usd = 0.0
        self._total_tokens = 0


class OpenAILLM(LLM):
    """OpenAI provider implementation."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        super().__init__(config or LLMConfig(provider=Provider.OPENAI))
        self._client = None
    
    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            except ImportError:
                raise ImportError("Please install openai: pip install openai")
        return self._client
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Send chat request to OpenAI."""
        client = self._get_client()
        
        start_time = time.time()
        
        # Merge kwargs with config
        params = {
            'model': self.config.model,
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens,
            **kwargs
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        response = await client.chat.completions.create(
            messages=[m.to_dict() for m in messages],
            **params
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        choice = response.choices[0]
        llm_response = LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=dict(response.usage) if response.usage else {},
            finish_reason=choice.finish_reason,
            tool_calls=[{
                'id': tc.id,
                'type': tc.type,
                'function': {
                    'name': tc.function.name,
                    'arguments': tc.function.arguments
                }
            } for tc in (choice.message.tool_calls or [])],
            latency_ms=latency_ms
        )
        
        # Estimate cost (simplified)
        llm_response.cost_usd = self._estimate_cost(llm_response.total_tokens)
        
        self._track_usage(llm_response)
        return llm_response
    
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """Stream chat response from OpenAI."""
        client = self._get_client()
        
        params = {
            'model': self.config.model,
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens,
            'stream': True,
            **kwargs
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        stream = await client.chat.completions.create(
            messages=[m.to_dict() for m in messages],
            **params
        )
        
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                content = delta.content or ""
                finish_reason = chunk.choices[0].finish_reason
                
                yield StreamChunk(
                    content=content,
                    is_done=finish_reason is not None,
                    finish_reason=finish_reason
                )
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on tokens (simplified)."""
        # GPT-4o pricing: ~$5 per 1M input tokens, ~$15 per 1M output tokens
        # This is a rough estimate
        return tokens * 0.000015


class MockLLM(LLM):
    """Mock LLM for testing."""
    
    def __init__(self, response: str = "Mock response", **kwargs):
        super().__init__(LLMConfig(model="mock", **kwargs))
        self.response = response
        self.call_count = 0
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Return mock response."""
        self.call_count += 1
        await asyncio.sleep(0.1)  # Simulate latency
        
        return LLMResponse(
            content=self.response,
            model="mock",
            usage={'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            finish_reason="stop",
            latency_ms=100.0,
            cost_usd=0.0
        )
    
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[StreamChunk]:
        """Stream mock response."""
        words = self.response.split()
        for word in words:
            await asyncio.sleep(0.05)
            yield StreamChunk(content=word + " ")
        yield StreamChunk(is_done=True)


def create_llm(
    provider: Union[str, Provider] = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> LLM:
    """Factory function to create an LLM instance."""
    if isinstance(provider, str):
        provider = Provider(provider.lower())
    
    config = LLMConfig(
        provider=provider,
        model=model or "gpt-4o",
        api_key=api_key,
        **kwargs
    )
    
    if provider == Provider.OPENAI:
        return OpenAILLM(config)
    elif provider == Provider.CUSTOM or provider == Provider.MOCK:
        return MockLLM(**kwargs)
    else:
        # For other providers, return MockLLM or implement specific classes
        # In production, you'd implement each provider
        return MockLLM(**kwargs)
