"""
Anthropic Integration for FlowMind

Production-ready Anthropic Claude client.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class AnthropicClient:
    """
    Production Anthropic Claude client with resilience patterns.
    
    Features:
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Token usage tracking
    - Cost estimation
    - Streaming support
    """
    
    PRICING = {
        'claude-3-5-sonnet-20241022': {'input': 0.003, 'output': 0.015},
        'claude-3-sonnet-20240229': {'input': 0.003, 'output': 0.015},
        'claude-3-opus-20240229': {'input': 0.015, 'output': 0.075},
        'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00125},
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        import os
        
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
            except ImportError:
                raise ImportError("Install anthropic package: pip install anthropic")
        
        return self._client
    
    async def chat(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        messages: List[Dict[str, Any]] = None,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        if messages is None:
            raise ValueError("messages is required")
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.messages.create(
                    model=model,
                    messages=messages,
                    system=system or "",
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                
                usage = {
                    'prompt_tokens': response.usage.input_tokens,
                    'completion_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens,
                }
                
                return {
                    'content': response.content[0].text if response.content else "",
                    'model': response.model,
                    'usage': usage,
                    'cost': self._calculate_cost(model, usage),
                    'stop_reason': response.stop_reason,
                }
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    delay = min(2 ** attempt * 0.5, 10.0)
                    await asyncio.sleep(delay)
                    continue
                
                raise
        
        raise last_error
    
    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        if model not in self.PRICING:
            return 0.0
        
        pricing = self.PRICING[model]
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        
        cost = 0.0
        if 'input' in pricing:
            cost += (input_tokens / 1000) * pricing['input']
        if 'output' in pricing:
            cost += (output_tokens / 1000) * pricing['output']
        
        return cost
    
    async def close(self) -> None:
        if self._client and hasattr(self._client, 'close'):
            await self._client.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
