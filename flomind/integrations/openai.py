"""
FlowMind Integrations - OpenAI Provider

Production-ready OpenAI integration with:
- Automatic retry on rate limits
- Token usage tracking
- Cost estimation
- Streaming support
- Error handling
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio
import time
import os


@dataclass
class OpenAIConfig:
    """OpenAI provider configuration."""
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o"
    max_retries: int = 3
    timeout_seconds: float = 120.0
    
    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")


@dataclass
class TokenUsage:
    """Track token usage for cost estimation."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> 'TokenUsage':
        """Parse token usage from OpenAI response."""
        usage = response.get("usage", {})
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0)
        )


# Approximate pricing (update as needed)
PRICING = {
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},  # per 1K tokens
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
}


class OpenAIProvider:
    """
    Production-ready OpenAI client.
    
    Features:
    - Automatic retry with exponential backoff on rate limits
    - Token usage tracking
    - Cost estimation
    - Streaming support
    - Timeout handling
    """
    
    def __init__(self, config: Optional[OpenAIConfig] = None):
        self.config = config or OpenAIConfig()
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                    timeout=self.config.timeout_seconds
                )
            except ImportError:
                raise ImportError(
                    "Install openai package: pip install openai"
                )
        return self._client
    
    async def chat_completion(self, messages: List[Dict[str, str]],
                              model: Optional[str] = None,
                              temperature: float = 0.7,
                              tools: Optional[List[Dict[str, Any]]] = None,
                              **kwargs) -> Dict[str, Any]:
        """
        Get a chat completion from OpenAI.
        
        Returns dict with:
        - content: The response text
        - usage: TokenUsage object
        - cost_usd: Estimated cost
        - raw_response: Full API response
        """
        model = model or self.config.default_model
        client = self._get_client()
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    tools=tools,
                    **kwargs
                )
                
                # Parse response
                content = response.choices[0].message.content
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
                
                # Estimate cost
                cost = self._estimate_cost(usage, model)
                
                return {
                    "content": content,
                    "usage": usage,
                    "cost_usd": cost,
                    "raw_response": response
                }
                
            except Exception as e:
                last_error = e
                # Check if rate limit error (retry)
                if hasattr(e, 'status_code') and e.status_code == 429:
                    wait_time = (2 ** attempt) + (0.1 * attempt)  # Exponential + jitter
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        raise last_error
    
    async def chat_completion_stream(
        self, messages: List[Dict[str, str]],
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        model = model or self.config.default_model
        client = self._get_client()
        
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _estimate_cost(self, usage: TokenUsage, model: str) -> float:
        """Estimate cost based on token usage."""
        pricing = PRICING.get(model, PRICING["gpt-4o"])
        
        prompt_cost = (usage.prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (usage.completion_tokens / 1000) * pricing["completion"]
        
        return prompt_cost + completion_cost
