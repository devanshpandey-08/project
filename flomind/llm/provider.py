"""
LLM Provider abstraction for FlowMind.

Provides a unified interface for all LLM providers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import asyncio


class ChatRole(Enum):
    """Roles in a chat conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in a chat conversation."""
    role: ChatRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    
    @classmethod
    def system(cls, content: str) -> 'Message':
        return cls(role=ChatRole.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> 'Message':
        return cls(role=ChatRole.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str) -> 'Message':
        return cls(role=ChatRole.ASSISTANT, content=content)
    
    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> 'Message':
        return cls(role=ChatRole.TOOL, content=content, tool_call_id=tool_call_id)


@dataclass
class LLMResponse:
    """Response from an LLM."""
    content: str
    role: str = "assistant"
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    
    @property
    def total_tokens(self) -> int:
        if self.usage:
            return self.usage.get('total_tokens', 0)
        # Estimate: ~4 chars per token
        return len(self.content) // 4
    
    @property
    def cost_usd(self) -> float:
        # Simplified cost estimation (would be provider-specific in production)
        if not self.usage:
            return 0.0
        input_tokens = self.usage.get('prompt_tokens', 0)
        output_tokens = self.usage.get('completion_tokens', 0)
        # Assume $0.03/1K input, $0.06/1K output (GPT-4-like pricing)
        return (input_tokens * 0.00003) + (output_tokens * 0.00006)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    OLLAMA = "ollama"
    MOCK = "mock"


@dataclass
class LLMConfig:
    """Configuration for an LLM."""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 60.0


class LLM:
    """
    Unified LLM interface.
    
    Provides a consistent API across all LLM providers.
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
    
    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Send a chat request."""
        raise NotImplementedError
    
    async def complete(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """Send a completion request."""
        messages = [Message.user(prompt)]
        response = await self.chat(messages, **kwargs)
        return response.content
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert internal messages to provider format."""
        result = []
        for msg in messages:
            d = {
                'role': msg.role.value,
                'content': msg.content,
            }
            if msg.name:
                d['name'] = msg.name
            if msg.tool_call_id:
                d['tool_call_id'] = msg.tool_call_id
            result.append(d)
        return result


class MockLLM(LLM):
    """Mock LLM for testing."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.responses: List[str] = []
        self.call_count = 0
    
    async def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        self.call_count += 1
        
        # Return predefined response or generate one
        if self.responses and len(self.responses) >= self.call_count:
            content = self.responses[self.call_count - 1]
        else:
            content = f"Mock response to: {messages[-1].content[:50]}..."
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            usage={'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}
        )
    
    def set_response(self, response: str) -> None:
        """Set the next response."""
        self.responses.append(response)


def create_llm(
    provider: Union[str, LLMProvider] = "mock",
    model: Optional[str] = None,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    **kwargs
) -> LLM:
    """Factory function to create an LLM instance."""
    
    if isinstance(provider, str):
        provider = LLMProvider(provider.lower())
    
    config = LLMConfig(
        provider=provider,
        model=model or "gpt-4o",
        temperature=temperature,
        api_key=api_key,
        **kwargs
    )
    
    if provider == LLMProvider.MOCK:
        return MockLLM(config)
    
    elif provider == LLMProvider.OPENAI:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
            
            class OpenAILLM(LLM):
                async def chat(self, messages, tools=None, **kw):
                    kwargs = {**kw, 'temperature': self.config.temperature}
                    if tools:
                        kwargs['tools'] = tools
                    
                    response = await self._client.chat.completions.create(
                        model=self.config.model,
                        messages=self._convert_messages(messages),
                        **kwargs
                    )
                    
                    choice = response.choices[0]
                    return LLMResponse(
                        content=choice.message.content or "",
                        tool_calls=[tc.dict() for tc in choice.message.tool_calls] if choice.message.tool_calls else None,
                        finish_reason=choice.finish_reason,
                        usage=response.usage.dict() if response.usage else None,
                        model=response.model,
                    )
            
            llm = OpenAILLM(config)
            llm._client = client
            return llm
            
        except ImportError:
            raise ImportError("Install openai package: pip install openai")
    
    # Default to mock for other providers
    return MockLLM(config)
