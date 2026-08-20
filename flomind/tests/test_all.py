"""
FlowMind Comprehensive Test Suite

Production-grade tests covering:
- Unit tests for all components
- Integration tests
- Performance benchmarks
- Edge cases
"""

import asyncio
import pytest
from typing import Any, Dict
import time


# ============== Core Flow Tests ==============

class TestFlowState:
    """Tests for FlowState."""
    
    def test_state_creation(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        assert state.inputs == {}
        assert state.outputs == {}
        assert state.errors == []
    
    def test_state_set_get(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        state.set("key", "value")
        assert state.get("key") == "value"
        assert state.get("missing", "default") == "default"
    
    def test_state_add_input(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        state.add_input("input_key", "input_value")
        assert state.get("input_key") == "input_value"
    
    def test_state_snapshot(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        state.set("key1", "value1")
        state.take_snapshot(version=1)
        
        state.set("key1", "modified")
        assert state.restore_snapshot(1)
        assert state.get("key1") == "value1"
    
    def test_state_has_errors(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        assert not state.has_errors()
        
        state.add_error(ValueError("test error"))
        assert state.has_errors()
    
    def test_state_copy(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        state.set("key", "value")
        
        copied = state.copy()
        assert copied.get("key") == "value"
        assert copied is not state


class TestNode:
    """Tests for Node execution."""
    
    @pytest.mark.asyncio
    async def test_node_async_handler(self):
        from flomind.core.flow import Node, NodeConfig, NodeType
        from flomind.core.state import FlowState
        
        async def handler(state: FlowState):
            return {"result": "success"}
        
        node = Node(
            name="test_node",
            config=NodeConfig(name="test_node", node_type=NodeType.CUSTOM),
            handler=handler
        )
        
        state = FlowState()
        result = await node.execute(state)
        
        assert result.success
        assert result.output == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_node_sync_handler(self):
        from flomind.core.flow import Node, NodeConfig, NodeType
        from flomind.core.state import FlowState
        
        def handler(state: FlowState):
            return {"result": "sync_success"}
        
        node = Node(
            name="test_node",
            config=NodeConfig(name="test_node"),
            sync_handler=handler
        )
        
        state = FlowState()
        result = await node.execute(state)
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_node_error_handling(self):
        from flomind.core.flow import Node, NodeConfig
        from flomind.core.state import FlowState
        
        async def failing_handler(state: FlowState):
            raise ValueError("Intentional failure")
        
        node = Node(
            name="failing_node",
            config=NodeConfig(name="failing_node"),
            handler=failing_handler
        )
        
        state = FlowState()
        result = await node.execute(state)
        
        assert not result.success
        assert isinstance(result.error, ValueError)
    
    @pytest.mark.asyncio
    async def test_node_caching(self):
        from flomind.core.flow import Node, NodeConfig
        from flomind.core.state import FlowState
        import time
        
        call_count = 0
        
        async def handler(state: FlowState):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # Simulate work
            return {"result": "cached"}
        
        node = Node(
            name="cached_node",
            config=NodeConfig(name="cached_node", cache_enabled=True, cache_ttl_seconds=60),
            handler=handler
        )
        
        state = FlowState(inputs={"key": "value"})
        
        # First execution
        await node.execute(state)
        assert call_count == 1
        
        # Second execution (should use cache)
        await node.execute(state)
        assert call_count == 1  # Not called again
    
    @pytest.mark.asyncio
    async def test_node_timeout(self):
        from flomind.core.flow import Node, NodeConfig
        from flomind.core.state import FlowState
        import asyncio
        
        async def slow_handler(state: FlowState):
            await asyncio.sleep(10)
            return {"result": "too_slow"}
        
        node = Node(
            name="slow_node",
            config=NodeConfig(name="slow_node", timeout_seconds=0.1),
            handler=slow_handler
        )
        
        state = FlowState()
        
        with pytest.raises(asyncio.TimeoutError):
            await node.execute(state)


class TestFlow:
    """Tests for Flow execution."""
    
    @pytest.mark.asyncio
    async def test_flow_sequential_execution(self):
        from flomind import create_flow, FlowState
        
        flow = create_flow("sequential_test")
        
        @flow.add_node("step1")
        async def step1(state: FlowState):
            return {"step": 1}
        
        @flow.add_node("step2")
        async def step2(state: FlowState):
            prev = state.outputs.get("step1", {})
            return {"step": 2, "prev": prev}
        
        flow.add_edge("step1", "step2")
        flow.set_exit_points("step2")
        
        result = await flow.run(FlowState())
        
        assert result.outputs["step1"]["step"] == 1
        assert result.outputs["step2"]["step"] == 2
    
    @pytest.mark.asyncio
    async def test_flow_conditional_branching(self):
        from flomind import create_flow, FlowState, EdgeCondition
        
        flow = create_flow("conditional_test")
        
        @flow.add_node("decision")
        async def decision(state: FlowState):
            return {"value": state.get("flag", False)}
        
        @flow.add_node("true_branch")
        async def true_branch(state: FlowState):
            return {"branch": "true"}
        
        @flow.add_node("false_branch")
        async def false_branch(state: FlowState):
            return {"branch": "false"}
        
        flow.add_edge(
            "decision", "true_branch",
            condition=EdgeCondition.CUSTOM,
            condition_fn=lambda s: s.get("flag", False)
        )
        flow.add_edge(
            "decision", "false_branch",
            condition=EdgeCondition.CUSTOM,
            condition_fn=lambda s: not s.get("flag", False)
        )
        flow.set_exit_points("true_branch", "false_branch")
        
        # Test true branch
        result = await flow.run(FlowState(inputs={"flag": True}))
        assert "true_branch" in result.outputs
        
        # Test false branch
        result = await flow.run(FlowState(inputs={"flag": False}))
        assert "false_branch" in result.outputs
    
    @pytest.mark.asyncio
    async def test_flow_max_iterations(self):
        from flomind import create_flow, FlowState
        
        flow = create_flow("loop_test")
        
        @flow.add_node("loop_node")
        async def loop_node(state: FlowState):
            count = state.get("count", 0)
            return {"count": count + 1}
        
        flow.add_edge("loop_node", "loop_node")
        flow.set_entry_point("loop_node")
        
        result = await flow.run(FlowState(), max_iterations=5)
        
        assert result.has_errors()


# ============== Agent Tests ==============

class TestAgent:
    """Tests for Agent system."""
    
    @pytest.mark.asyncio
    async def test_agent_creation(self):
        from flomind.agents.agent import Agent, Role, AgentConfig
        
        agent = Agent.create(
            name="test_agent",
            role=Role.RESEARCHER,
            model="gpt-4o"
        )
        
        assert agent.config.name == "test_agent"
        assert agent.config.role == Role.RESEARCHER
    
    @pytest.mark.asyncio
    async def test_agent_with_tools(self):
        from flomind import Agent, Tool, tool
        
        @tool
        async def calculator(expression: str) -> float:
            """Calculate mathematical expression."""
            return eval(expression)
        
        agent = Agent.create(
            name="math_agent",
            tools=[calculator]
        )
        
        assert len(agent.config.tools) == 1
        assert agent.config.tools[0].name == "calculator"
    
    @pytest.mark.asyncio
    async def test_agent_mock_execution(self):
        from flomind import Agent
        from flomind.llm.provider import MockLLM, LLMConfig, LLMProvider
        
        llm = MockLLM(LLMConfig(provider=LLMProvider.MOCK, model="mock"))
        llm.set_response("This is a mock response")
        
        agent = Agent.create(name="mock_agent", model="mock")
        agent.llm = llm
        
        result = await agent.run("Test task")
        
        assert result.success
        assert "mock response" in result.output.lower()


class TestAgentTeam:
    """Tests for multi-agent teams."""
    
    @pytest.mark.asyncio
    async def test_team_creation(self):
        from flomind import AgentTeam, Agent, Role
        
        team = AgentTeam.create("research_team", strategy="sequential")
        
        team.add_agent(Agent.create("manager", role=Role.MANAGER))
        team.add_agent(Agent.create("researcher", role=Role.RESEARCHER))
        
        assert len(team.agents) == 2
    
    @pytest.mark.asyncio
    async def test_team_parallel_execution(self):
        from flomind import AgentTeam, Agent
        from flomind.llm.provider import MockLLM, LLMConfig, LLMProvider
        
        team = AgentTeam.create("parallel_team", strategy="parallel")
        
        # Create mock agents
        for i in range(3):
            agent = Agent.create(f"agent_{i}")
            agent.llm = MockLLM(LLMConfig(provider=LLMProvider.MOCK))
            agent.llm.set_response(f"Response from agent_{i}")
            team.add_agent(agent)
        
        result = await team.run("Test task")
        
        assert result.success
        assert len(result.results) == 3


# ============== Policy Tests ==============

class TestRetryPolicy:
    """Tests for retry policy."""
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        from flomind.policies.retry import RetryPolicy
        
        policy = RetryPolicy(max_retries=3)
        
        async def success_func():
            return "success"
        
        result = await policy.execute(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_after_failures(self):
        from flomind.policies.retry import RetryPolicy
        
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        
        attempts = 0
        
        async def fail_then_succeed():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("Temporary failure")
            return "finally success"
        
        result = await policy.execute(fail_then_succeed)
        assert result == "finally success"
        assert attempts == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        from flomind.policies.retry import RetryPolicy
        
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        
        async def always_fail():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            await policy.execute(always_fail)


class TestTimeoutPolicy:
    """Tests for timeout policy."""
    
    @pytest.mark.asyncio
    async def test_timeout_completes_in_time(self):
        from flomind.policies.timeout import TimeoutPolicy
        import asyncio
        
        policy = TimeoutPolicy(timeout_seconds=1.0)
        
        async def fast_func():
            await asyncio.sleep(0.1)
            return "completed"
        
        result = await policy.execute(fast_func)
        assert result == "completed"
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        from flomind.policies.timeout import TimeoutPolicy
        import asyncio
        
        policy = TimeoutPolicy(timeout_seconds=0.1, raise_on_timeout=True)
        
        async def slow_func():
            await asyncio.sleep(10)
            return "too slow"
        
        with pytest.raises(asyncio.TimeoutError):
            await policy.execute(slow_func)


class TestCircuitBreaker:
    """Tests for circuit breaker."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed(self):
        from flomind.policies.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3)
        
        async def success_func():
            return "success"
        
        result = await cb.execute(success_func)
        assert result == "success"
        assert cb.state == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        from flomind.policies.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
        
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        
        async def fail_func():
            raise ValueError("Failure")
        
        # Cause failures to open circuit
        for _ in range(3):
            try:
                await cb.execute(fail_func)
            except ValueError:
                pass
        
        assert cb.state == "open"
        
        # Should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            await cb.execute(fail_func)


# ============== Memory Tests ==============

class TestShortTermMemory:
    """Tests for short-term memory."""
    
    @pytest.mark.asyncio
    async def test_memory_add_get(self):
        from flomind.memory.memory import ShortTermMemory
        
        memory = ShortTermMemory(max_messages=10)
        
        await memory.add("First message")
        await memory.add("Second message")
        
        entries = await memory.get("query", limit=5)
        assert len(entries) == 2
    
    @pytest.mark.asyncio
    async def test_memory_capacity_limit(self):
        from flomind.memory.memory import ShortTermMemory
        
        memory = ShortTermMemory(max_messages=5)
        
        for i in range(10):
            await memory.add(f"Message {i}")
        
        assert memory.size == 5
    
    @pytest.mark.asyncio
    async def test_memory_clear(self):
        from flomind.memory.memory import ShortTermMemory
        
        memory = ShortTermMemory()
        
        await memory.add("Test message")
        await memory.clear()
        
        assert memory.size == 0


# ============== Tool Tests ==============

class TestTool:
    """Tests for tool system."""
    
    @pytest.mark.asyncio
    async def test_tool_decorator(self):
        from flomind import tool
        
        @tool
        async def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b
        
        result = await add.execute(a=5, b=3)
        assert result == 8
    
    @pytest.mark.asyncio
    async def test_tool_sync_function(self):
        from flomind import tool
        
        @tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b
        
        result = await multiply.execute(a=4, b=7)
        assert result == 28
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        from flomind import tool, ToolError
        
        @tool
        async def failing_tool(x: str) -> str:
            """Always fails."""
            raise ValueError("Tool failed")
        
        with pytest.raises(ToolError):
            await failing_tool.execute(x="test")
    
    def test_tool_openai_format(self):
        from flomind import Tool, ToolParameter
        
        tool_obj = Tool.create(
            name="search",
            description="Search for information",
            handler=lambda x: x,
            parameters=[
                ToolParameter("query", "string", "Search query", required=True),
                ToolParameter("limit", "integer", "Max results", required=False, default=10),
            ]
        )
        
        format_dict = tool_obj.to_openai_format()
        
        assert format_dict["function"]["name"] == "search"
        assert "query" in format_dict["function"]["parameters"]["properties"]


# ============== Vector Store Tests ==============

class TestInMemoryVectorStore:
    """Tests for in-memory vector store."""
    
    @pytest.mark.asyncio
    async def test_vector_store_add_search(self):
        from flomind.vector.store import InMemoryVectorStore, Document
        
        store = InMemoryVectorStore()
        
        docs = [
            Document.create(content="Machine learning is amazing"),
            Document.create(content="Deep learning uses neural networks"),
            Document.create(content="Python is great for ML"),
        ]
        
        ids = await store.add(docs)
        assert len(ids) == 3
        
        results = await store.search("neural networks", limit=2)
        assert len(results) == 2
        assert "neural" in results[0].content.lower()
    
    @pytest.mark.asyncio
    async def test_vector_store_metadata_filter(self):
        from flomind.vector.store import InMemoryVectorStore, Document
        
        store = InMemoryVectorStore()
        
        docs = [
            Document.create(content="Doc A", category="tech"),
            Document.create(content="Doc B", category="science"),
            Document.create(content="Doc C", category="tech"),
        ]
        
        await store.add(docs)
        
        results = await store.search(
            "document",
            limit=5,
            filter_metadata={"category": "tech"}
        )
        
        assert len(results) == 2
        assert all(d.metadata.get("category") == "tech" for d in results)
    
    @pytest.mark.asyncio
    async def test_vector_store_delete(self):
        from flomind.vector.store import InMemoryVectorStore, Document
        
        store = InMemoryVectorStore()
        
        docs = [Document.create(content=f"Doc {i}") for i in range(5)]
        ids = await store.add(docs)
        
        await store.delete([ids[0], ids[1]])
        
        assert store.size == 3


# ============== Streaming Tests ==============

class TestStream:
    """Tests for streaming system."""
    
    @pytest.mark.asyncio
    async def test_stream_write_read(self):
        from flomind.streaming.stream import Stream
        
        stream = Stream()
        
        await stream.write("chunk1")
        await stream.write("chunk2")
        await stream.end()
        
        chunks = []
        async for chunk in stream.iter():
            if not chunk.is_done:
                chunks.append(chunk.content)
        
        assert chunks == ["chunk1", "chunk2"]
    
    @pytest.mark.asyncio
    async def test_event_bus_pub_sub(self):
        from flomind.streaming.stream import EventBus, StreamEvent, EventType
        
        bus = EventBus()
        received_events = []
        
        async def handler(event):
            received_events.append(event)
        
        bus.subscribe(EventType.CHUNK, handler)
        
        event = StreamEvent(event_type=EventType.CHUNK, payload="test")
        await bus.publish(event)
        
        assert len(received_events) == 1
        assert received_events[0].payload == "test"


# ============== Observability Tests ==============

class TestTracer:
    """Tests for tracing system."""
    
    def test_trace_creation(self):
        from flomind.observability.tracer import Tracer
        
        tracer = Tracer(service_name="test")
        trace = tracer.start_trace("test_trace", key="value")
        
        assert trace.name == "test_trace"
        assert trace.metadata["key"] == "value"
    
    def test_span_creation(self):
        from flomind.observability.tracer import Tracer
        
        tracer = Tracer()
        trace = tracer.start_trace("parent_trace")
        
        span = tracer.start_span("child_span", trace_id=trace.id, kind="operation")
        
        assert span.name == "child_span"
        assert span.parent_id == trace.id
    
    def test_trace_duration(self):
        from flomind.observability.tracer import Tracer
        import time
        
        tracer = Tracer()
        trace = tracer.start_trace("timed_trace")
        
        time.sleep(0.1)
        
        tracer.end_trace(trace.id)
        
        assert trace.duration_ms >= 100  # At least 100ms


class TestMetrics:
    """Tests for metrics collection."""
    
    def test_counter_increment(self):
        from flomind.observability.tracer import Metrics
        
        metrics = Metrics()
        
        metrics.inc("requests")
        metrics.inc("requests", 5)
        
        assert metrics.get_counter("requests") == 6
    
    def test_gauge_set(self):
        from flomind.observability.tracer import Metrics
        
        metrics = Metrics()
        
        metrics.set("temperature", 25.5)
        
        assert metrics.get_gauge("temperature") == 25.5
    
    def test_histogram_observe(self):
        from flomind.observability.tracer import Metrics
        
        metrics = Metrics()
        
        for val in [10, 20, 30, 40, 50]:
            metrics.observe("latency", val)
        
        stats = metrics.get_histogram("latency")
        
        assert stats['count'] == 5
        assert stats['avg'] == 30
        assert stats['min'] == 10
        assert stats['max'] == 50


# ============== Configuration Tests ==============

class TestConfiguration:
    """Tests for configuration system."""
    
    def test_config_from_dict(self):
        from flomind.config.config import FlowMindConfig
        
        data = {
            'environment': 'production',
            'debug': False,
            'llm': {
                'provider': 'anthropic',
                'model': 'claude-3-sonnet',
            },
            'observability': {
                'enabled': True,
                'log_level': 'WARNING',
            }
        }
        
        config = FlowMindConfig.from_dict(data)
        
        assert config.environment == "production"
        assert config.llm.provider == "anthropic"
        assert config.observability.log_level == "WARNING"
    
    def test_config_validation(self):
        from flomind.config.config import FlowMindConfig
        
        config = FlowMindConfig()
        config.llm.temperature = 2.5  # Invalid
        
        errors = config.validate()
        
        assert any("temperature" in e for e in errors)
    
    def test_config_environment_check(self):
        from flomind.config.config import FlowMindConfig
        
        prod_config = FlowMindConfig(environment="production")
        dev_config = FlowMindConfig(environment="development")
        
        assert prod_config.is_production()
        assert dev_config.is_development()


# ============== Performance Benchmarks ==============

class TestPerformance:
    """Performance benchmarks."""
    
    @pytest.mark.asyncio
    async def test_flow_execution_speed(self):
        from flomind import create_flow, FlowState
        
        flow = create_flow("perf_test")
        
        # Add 10 simple nodes
        for i in range(10):
            @flow.add_node(f"node_{i}")
            async def handler(state: FlowState, idx=i):
                return {"idx": idx}
            
            if i > 0:
                flow.add_edge(f"node_{i-1}", f"node_{i}")
        
        flow.set_exit_points("node_9")
        
        start = time.time()
        await flow.run(FlowState())
        elapsed = time.time() - start
        
        # Should complete 10 nodes in under 1 second
        assert elapsed < 1.0, f"Flow took {elapsed}s, expected < 1s"
    
    @pytest.mark.asyncio
    async def test_state_copy_performance(self):
        from flomind.core.state import FlowState
        
        state = FlowState()
        
        # Add lots of data
        for i in range(1000):
            state.set(f"key_{i}", f"value_{i}")
        
        start = time.time()
        
        for _ in range(100):
            copied = state.copy()
        
        elapsed = time.time() - start
        
        # 100 copies should take less than 0.5 seconds
        assert elapsed < 0.5, f"Copies took {elapsed}s"


# Run tests with: pytest tests/test_all.py -v
