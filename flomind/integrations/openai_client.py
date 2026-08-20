"""
OpenAI Integration for FlowMind

Production-ready OpenAI client with:
- Automatic retry with exponential backoff
- Rate limiting handling
- Token counting and cost tracking
- Streaming support
- Error handling and logging
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, AsyncIterator
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    Production OpenAI client with resilience patterns.
    
    Features:
    - Automatic retries with exponential backoff
    - Rate limit handling (429 errors)
    - Token usage tracking
    - Cost estimation
    - Streaming support
    - Connection pooling
    """
    
    # Pricing per 1K tokens (as of 2024)
    PRICING = {
        'gpt-4o': {'input': 0.005, 'output': 0.015},
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
        'text-embedding-3-small': {'input': 0.00002},
        'text-embedding-3-large': {'input': 0.00013},
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        rate_limit_max_retries: int = 10,
    ):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            organization: Organization ID
            base_url: Custom base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retries for non-rate-limit errors
            rate_limit_max_retries: Maximum retries for rate limit errors
        """
        import os
        
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.organization = organization or os.getenv('OPENAI_ORG_ID')
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_max_retries = rate_limit_max_retries
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self._client = None
    
    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                kwargs = {
                    'api_key': self.api_key,
                    'timeout': self.timeout,
                }
                if self.organization:
                    kwargs['organization'] = self.organization
                if self.base_url:
                    kwargs['base_url'] = self.base_url
                
                self._client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise ImportError("Install openai package: pip install openai")
        
        return self._client
    
    async def chat(
        self,
        model: str = "gpt-4o",
        messages: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat completion request.
        
        Args:
            model: Model to use
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            tools: List of tools for function calling
            tool_choice: Tool choice strategy
            stream: Whether to stream the response
            
        Returns:
            Response dictionary with content, usage, and cost
        """
        if messages is None:
            raise ValueError("messages is required")
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    tools=tools,
                    tool_choice=tool_choice,
                    stream=stream,
                    **kwargs
                )
                
                # Process response
                if stream:
                    return self._process_stream_response(response)
                
                choice = response.choices[0]
                usage = response.usage.dict() if response.usage else {}
                
                return {
                    'content': choice.message.content or "",
                    'role': choice.message.role,
                    'finish_reason': choice.finish_reason,
                    'tool_calls': [
                        {
                            'id': tc.id,
                            'type': tc.type,
                            'function': {
                                'name': tc.function.name,
                                'arguments': tc.function.arguments,
                            }
                        }
                        for tc in (choice.message.tool_calls or [])
                    ] if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls else [],
                    'usage': usage,
                    'model': response.model,
                    'cost': self._calculate_cost(model, usage),
                }
                
            except Exception as e:
                last_error = e
                
                # Check if rate limited
                if hasattr(e, 'status_code') and e.status_code == 429:
                    if attempt < self.rate_limit_max_retries:
                        # Exponential backoff for rate limits
                        delay = min(2 ** attempt * 1.0, 60.0)
                        logger.warning(f"Rate limited, waiting {delay}s before retry")
                        await asyncio.sleep(delay)
                        continue
                
                # Regular retry for other errors
                if attempt < self.max_retries:
                    delay = min(2 ** attempt * 0.5, 10.0)
                    logger.warning(f"Request failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                    continue
                
                raise
        
        raise last_error
    
    async def chat_stream(
        self,
        model: str = "gpt-4o",
        messages: List[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream chat completion.
        
        Yields:
            Content chunks as they arrive
        """
        result = await self.chat(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in result['stream']:
            yield chunk
    
    async def embeddings(
        self,
        text: str | List[str],
        model: str = "text-embedding-3-small",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate embeddings.
        
        Args:
            text: Text or list of texts to embed
            model: Embedding model to use
            
        Returns:
            Embeddings with usage and cost
        """
        if isinstance(text, str):
            text = [text]
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.embeddings.create(
                    model=model,
                    input=text,
                    **kwargs
                )
                
                embeddings = [e.embedding for e in response.data]
                usage = response.usage.dict() if response.usage else {}
                
                return {
                    'embeddings': embeddings,
                    'usage': usage,
                    'model': response.model,
                    'cost': self._calculate_cost(model, usage),
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
        """Calculate cost based on token usage."""
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
    
    def _process_stream_response(self, response) -> Dict[str, Any]:
        """Process streaming response."""
        async def stream_generator():
            content = ""
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    content += delta
                    yield delta
        
        return {'stream': stream_generator()}
    
    async def close(self) -> None:
        """Close the client connection."""
        if self._client and hasattr(self._client, 'close'):
            await self._client.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
