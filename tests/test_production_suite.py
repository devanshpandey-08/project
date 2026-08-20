"""
FlowMind Production Test Suite

Tests the REAL production scenarios:
1. Debugging when a 10-node flow fails at step 7
2. State recovery after rate limit errors
3. Observability into token usage and latency per step
4. Developer experience - how fast can you understand the codebase
"""

import asyncio
import pytest
from datetime import datetime

# Import core components
from flomind.core.flow import Flow, FlowBuilder, FlowConfig
from flomind.core.node import Node, NodeType, NodeConfig
from flomind.core.state import State, StateSnapshot

# Import observability
from flomind.observability.tracer import FlowTracer, Trace, Span
from flomind.observability.debugger import FlowDebugger
from flomind.observability.metrics import MetricsCollector

# Import resilience
from flomind.resilience.retry import RetryStrategy, CircuitBreaker, ResilientExecutor

# Import tools
from flomind.tools.tool import Tool, tool
from flomind.tools.registry import ToolRegistry

# Import memory
from flomind.memory.short_term import ShortTermMemory


# ============================================================================
# TEST 1: Debugging - When flow fails at step 7, see what happened at steps 1-6
# ============================================================================

class TestDebuggingExperience:
    """Test the key differentiator: debugging complex flows."""
    
    @pytest.mark.asyncio
    async def test_state_history_after_failure(self):
        """When flow fails at node 7, inspect state at nodes 1-6."""
        
        execution_log = []
        
        def make_node_func(node_id: str, should_fail: bool = False):
            async def func(**kwargs):
                execution_log.append(f"{node_id}_start")
                if should_fail:
                    raise ValueError(f"Simulated failure at {node_id}")
                return f"result_from_{node_id}"
            return func
        
        # Build a 10-node flow where node 7 fails
        builder = FlowBuilder("debug_test_flow")
        
        for i in range(1, 11):
            should_fail = (i == 7)
            builder.add_node(
                id=f"node_{i}",
                func=make_node_func(f"node_{i}", should_fail),
                node_type=NodeType.TASK,
                inputs=[],
                retry_count=0  # No retries for this test
            )
            
            if i > 1:
                builder.connect(f"node_{i-1}", f"node_{i}")
        
        flow = builder.start_at("node_1").build()
        
        # Execute and expect failure
        state = await flow.execute({})
        
        # Verify we can see what happened before failure
        assert len(execution_log) >= 6, "Should have executed at least 6 nodes"
        
        # Check state history - can we see what happened at each step?
        failed_nodes = state.get_failed_nodes()
        assert "node_7" in failed_nodes, "Node 7 should be in failed nodes"
        
        # Get node history for debugging
        node_6_history = state.get_node_history("node_6")
        assert len(node_6_history) > 0, "Should have history for node 6"
        
        # Verify debug string is helpful
        debug_output = state.debug_string()
        assert "Failed nodes" in debug_output
        assert "node_7" in debug_output
        
        print("\n=== DEBUG OUTPUT ===")
        print(debug_output)
        print("====================\n")
    
    @pytest.mark.asyncio
    async def test_trace_debug_report(self):
        """Test comprehensive debug report generation."""
        
        tracer = FlowTracer()
        debugger = FlowDebugger()
        
        # Create a trace with multiple spans
        trace = tracer.start_trace("test_flow")
        
        span1 = tracer.start_span(trace.trace_id, "fetch_data", kind="tool")
        tracer.finish_span(span1.span_id, success=True, output_data={"data": "test"})
        
        span2 = tracer.start_span(trace.trace_id, "process", kind="node")
        tracer.finish_span(span2.span_id, success=True, output_data={"processed": True})
        
        span3 = tracer.start_span(trace.trace_id, "llm_call", kind="llm")
        tracer.finish_span(span3.span_id, success=False, error="Rate limit exceeded",
                          tokens_used=150)
        
        tracer.finish_trace(trace.trace_id)
        debugger.attach_trace(trace)
        
        # Generate debug report
        report = debugger.generate_debug_report(trace.trace_id)
        
        assert "FLOW TRACE REPORT" in report
        assert "Failed" in report  # Status should show failed
        assert "llm_call" in report
        assert "Rate limit" in report
        
        print("\n=== DEBUG REPORT ===")
        print(report)
        print("====================\n")


# ============================================================================
# TEST 2: State Recovery After Rate Limit Errors
# ============================================================================

class TestStateRecovery:
    """Test recovery from transient failures like rate limits."""
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """Test retry strategy handles rate limits correctly."""
        
        call_count = 0
        
        async def flaky_api():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Rate limit exceeded (429)")
            return "success"
        
        retry_strategy = RetryStrategy(
            max_retries=3,
            base_delay=0.01,  # Fast for testing
            jitter=False
        )
        
        executor = ResilientExecutor(retry_strategy=retry_strategy)
        
        result = await executor.execute(flaky_api)
        
        assert result == "success"
        assert call_count == 3, "Should have retried twice before success"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker prevents cascade failures."""
        
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1  # Fast for testing
        )
        
        # Simulate failures
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state.value == "open", "Circuit should be open after 3 failures"
        assert not cb.can_execute(), "Should not allow execution when open"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should transition to half-open
        assert cb.can_execute(), "Should allow test call after timeout"
        assert cb.state.value == "half_open"


# ============================================================================
# TEST 3: Observability - Token Usage and Latency Per Step
# ============================================================================

class TestObservability:
    """Test token tracking and latency breakdown."""
    
    def test_trace_token_tracking(self):
        """Track tokens used by each node."""
        
        tracer = FlowTracer()
        trace = tracer.start_trace("llm_flow")
        
        # Simulate LLM node with token usage
        span1 = tracer.start_span(trace.trace_id, "summarize", kind="llm")
        tracer.finish_span(span1.span_id, success=True, 
                          tokens_used=500, cost_usd=0.0025)
        
        span2 = tracer.start_span(trace.trace_id, "translate", kind="llm")
        tracer.finish_span(span2.span_id, success=True,
                          tokens_used=300, cost_usd=0.0015)
        
        tracer.finish_trace(trace.trace_id)
        
        # Verify totals
        assert trace.total_tokens == 800
        assert abs(trace.total_cost_usd - 0.004) < 0.0001
        
        # Verify latency breakdown
        breakdown = trace.get_latency_breakdown()
        assert "llm" in breakdown
    
    def test_metrics_aggregation(self):
        """Test aggregate metrics collection."""
        
        collector = MetricsCollector()
        tracer = FlowTracer()
        
        # Record multiple traces
        for i in range(5):
            trace = tracer.start_trace(f"flow_{i}")
            span = tracer.start_span(trace.trace_id, "process")
            tracer.finish_span(span.span_id, success=(i != 3))  # One failure
            tracer.finish_trace(trace.trace_id)
            
            collector.record_execution(trace)
        
        summary = collector.get_summary()
        
        assert summary["total_executions"] == 5
        assert summary["success_rate"] == "80.00%"  # 4/5 successful


# ============================================================================
# TEST 4: Developer Experience - Simple API for Complex Flows
# ============================================================================

class TestDeveloperExperience:
    """Test how easy it is to build and understand flows."""
    
    @pytest.mark.asyncio
    async def test_fluent_builder_api(self):
        """Test the fluent builder makes flow creation intuitive."""
        
        def fetch(query: str) -> str:
            return f"results_for_{query}"
        
        def process(data: str) -> str:
            return f"processed_{data}"
        
        # Fluent API should be readable
        flow = (FlowBuilder("search_flow")
            .add_node("fetch", fetch, inputs=["query"])
            .add_node("process", process, inputs=["data"])
            .connect("fetch", "process")
            .start_at("fetch")
            .end_at("process")
            .build())
        
        # Visualize should help understand the flow
        visualization = flow.visualize()
        
        assert "search_flow" in visualization
        assert "fetch" in visualization
        assert "process" in visualization
        assert "└─>" in visualization  # Shows connections
        
        print("\n=== FLOW VISUALIZATION ===")
        print(visualization)
        print("==========================\n")
    
    @pytest.mark.asyncio
    async def test_tool_decorator_simplicity(self):
        """Test tool decorator makes tool creation simple."""
        
        @tool(description="Search for information")
        def search(query: str) -> str:
            """Search the web for information."""
            return f"Results for: {query}"
        
        # Should automatically create Tool with schema
        assert isinstance(search, Tool)
        assert search.name == "search"
        assert "Search" in search.description
        
        # Should generate OpenAI schema
        schema = search.to_openai_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "parameters" in schema["function"]
    
    @pytest.mark.asyncio
    async def test_memory_is_intuitive(self):
        """Test memory API is simple and clear."""
        
        memory = ShortTermMemory(max_messages=5)
        
        # Add messages naturally
        memory.add_message("user", "Hello!")
        memory.add_message("assistant", "Hi there!")
        memory.add_message("user", "How are you?")
        
        # Get messages in OpenAI format
        messages = memory.get_messages()
        
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
        
        # Token counting should work
        token_count = memory.get_token_count()
        assert token_count > 0


# ============================================================================
# TEST 5: Parallel Execution (Real Performance Test)
# ============================================================================

class TestParallelExecution:
    """Test true parallel execution for performance."""
    
    @pytest.mark.asyncio
    async def test_parallel_node_execution(self):
        """Test nodes execute in parallel when possible."""
        
        execution_times = {}
        
        async def slow_node(node_id: str, delay: float):
            start = datetime.utcnow()
            await asyncio.sleep(delay)
            end = datetime.utcnow()
            execution_times[node_id] = {
                "start": start,
                "end": end,
                "duration": (end - start).total_seconds()
            }
            return f"result_{node_id}"
        
        # Create flow with 3 parallel nodes
        builder = FlowBuilder("parallel_test")
        
        builder.add_node("parallel_1", lambda: slow_node("p1", 0.1), node_type=NodeType.TASK)
        builder.add_node("parallel_2", lambda: slow_node("p2", 0.1), node_type=NodeType.TASK)
        builder.add_node("parallel_3", lambda: slow_node("p3", 0.1), node_type=NodeType.TASK)
        
        # All start from entry, no connections = parallel
        flow = builder.build()
        
        start_time = datetime.utcnow()
        state = await flow.execute({})
        total_time = (datetime.utcnow() - start_time).total_seconds()
        
        # If truly parallel, total time should be ~0.1s, not ~0.3s
        # Allow some overhead
        assert total_time < 0.3, f"Should execute in parallel, took {total_time}s"
        
        print(f"\nParallel execution completed in {total_time:.3f}s\n")


# ============================================================================
# Run all tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
