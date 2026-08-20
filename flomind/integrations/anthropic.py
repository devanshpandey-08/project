"""
FlowMind Integrations - Anthropic Provider

Production-ready Anthropic (Claude) integration with:
- Automatic retry on rate limits
- Token usage tracking
- Cost estimation
- Streaming support
"""

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio
import os


@dataclass
class AnthropicConfig:
    """Anthropic provider configuration."""
    api_key: Optional[str] = None
    default_model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3
    timeout_seconds: float = 120.0
    
    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")


# Approximate pricing (update as needed)
ANTHROPIC_PRICING = {
    "claude-3-5-sonnet-20241022": {"prompt": 0.003, "completion": 0.015},  # per 1K tokens
    "claude-3-opus-20240229": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet-20240229": {"prompt": 0.003, "completion": 0.015},
    "claude-3-haiku-20240307": {"prompt": 0.00025, "completion": 0.00125},
}


class AnthropicProvider:
    """
    Production-ready Anthropic client.
    
    Features:
    - Automatic retry with exponential backoff
    - Token usage tracking
    - Cost estimation
    - Streaming support
    """
    
    def __init__(self, config: Optional[AnthropicConfig] = None):
        self.config = config or AnthropicConfig()
        self._client = None
    
    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout_seconds
                )
            except ImportError:
                raise ImportError(
                    "Install anthropic package: pip install anthropic"
                )
        return self._client
    
    async def chat_completion(self, messages: List[Dict[str, str]],
                              model: Optional[str] = None,
                              max_tokens: int = 1024,
                              **kwargs) -> Dict[str, Any]:
        """
        Get a chat completion from Anthropic.
        
        Returns dict with:
        - content: The response text
        - usage: Token usage info
        - cost_usd: Estimated cost
        """
        model = model or self.config.default_model
        client = self._get_client()
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                # Convert messages to Anthropic format
                system_message = ""
                anthropic_messages = []
                
                for msg in messages:
                    if msg["role"] == "system":
                        system_message = msg["content"]
                    else:
                        anthropic_messages.append({
                            "role": "user" if msg["role"] == "user" else "assistant",
                            "content": msg["content"]
                        })
                
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_message,
                    messages=anthropic_messages,
                    **kwargs
                )
                
                content = response.content[0].text if response.content else ""
                
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
                
                cost = self._estimate_cost(usage, model)
                
                return {
                    "content": content,
                    "usage": usage,
                    "cost_usd": cost,
                    "raw_response": response
                }
                
            except Exception as e:
                last_error = e
                # Check if rate limit error
                if hasattr(e, 'status_code') and e.status_code == 429:
                    wait_time = (2 ** attempt) + (0.1 * attempt)
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        raise last_error
    
    async def chat_completion_stream(
        self, messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        model = model or self.config.default_model
        client = self._get_client()
        
        system_message = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })
        
        stream = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_message,
            messages=anthropic_messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if chunk.type == "content_block_delta" and chunk.delta.text:
                yield chunk.delta.text
    
    def _estimate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Estimate cost based on token usage."""
        pricing = ANTHROPIC_PRICING.get(model, ANTHROPIC_PRICING["claude-3-5-sonnet-20241022"])
        
        prompt_cost = (usage["input_tokens"] / 1000) * pricing["prompt"]
        completion_cost = (usage["output_tokens"] / 1000) * pricing["completion"]
        
        return prompt_cost + completion_cost
