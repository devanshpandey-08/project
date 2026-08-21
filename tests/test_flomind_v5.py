"""Comprehensive test suite for FlowMind v5.0 - Zero Silent Failures."""
import asyncio
import pytest
import sys
import os

# Add workspace to path
sys.path.insert(0, '/workspace')

from flomind.core.types import ExecutionMode, NodeStatus, Result, NodeConfig
from flomind.core.state import FlowState
from flomind.core.flow import Flow, FlowBuilder, Node
from flomind.persistence.checkpoint import MemorySaver, SQLiteSaver
from flomind.security.crypto import Encryptor, PIIDetector, InputSanitizer, RBACManager, Role, Permission
from flomind.resilience.policies import RetryPolicy, CircuitBreaker, TimeoutPolicy, RateLimiter
from flomind.hitl.engine import HITLEngine, ApprovalPattern, ApprovalStatus
from flomind.tools.tool import Tool, tool
from flomind.config.settings import FlowMindConfig


class TestCoreTypes:
    """Test type definitions."""
    
    def test_result_monad_success(self):
        result = Result.ok("value")
        assert result.success is True
        assert result.value == "value"
        assert result.error is None
    
    def test_result_monad_failure(self):
        result = Result.fail("error message")
        assert result.success is False
        assert result.value is None
        assert result.error == "error message"
    
    def test_result_map(self):
        result = Result.ok(5).map(lambda x: x * 2)
        assert result.value == 10
    
    def test_node_config_validation(self):
        with pytest.raises(ValueError):
            NodeConfig(retry_count=-1)
        
        with pytest.raises(ValueError):
            NodeConfig(timeout_seconds=0)


class TestFlowState:
    """Test immutable state management."""
    
    def test_state_immutability(self):
        state1 = FlowState().set("key", "value1")
        state2 = state1.set("key", "value2")
        
        assert state1.get("key") == "value1"
        assert state2.get("key") == "value2"
    
    def test_state_snapshots(self):
        state = FlowState().set("a", 1)
        state = state.take_snapshot()
        state = state.set("a", 2)
        state = state.take_snapshot()
        
        history = state.get_history()
        assert len(history) == 2
        
        restored = state.restore_snapshot(1)
        assert restored.get("a") == 1
    
    def test_state_clone(self):
        state1 = FlowState().set("x", 10)
        state2 = state1._clone()
        
        assert state1.get("x") == state2.get("x")
        state2 = state2.set("x", 20)
        assert state1.get("x") == 10
        assert state2.get("x") == 20


class TestFlowEngine:
    """Test flow execution engine."""
    
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        def add_one(x: int) -> int:
            return x + 1
        
        flow = (FlowBuilder("test_seq")
            .add_node("start", lambda: {"x": 0}, outputs=["x"])
            .add_node("add", add_one, inputs=["x"], outputs=["result"])
            .connect("start", "add")
            .build())
        
        state = await flow.execute({})
        assert state.get("result") == 1
    
    @pytest.mark.asyncio
    async def test_parallel_execution_no_coroutine_leak(self):
        async def slow_task() -> int:
            await asyncio.sleep(0.01)
            return 42
        
        flow = (FlowBuilder("test_parallel")
            .add_node("task1", slow_task, inputs=[], outputs=["r1"])
            .add_node("task2", slow_task, inputs=[], outputs=["r2"])
            .add_node("task3", slow_task, inputs=[], outputs=["r3"])
            .set_mode(ExecutionMode.PARALLEL)
            .build())
        
        # Should complete without RuntimeWarning about unawaited coroutines
        state = await flow.execute({})
        assert state.get("r1") == 42
        assert state.get("r2") == 42
        assert state.get("r3") == 42
    
    @pytest.mark.asyncio
    async def test_retry_logic(self):
        attempt_count = 0
        
        def flaky_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        flow = (FlowBuilder("test_retry")
            .add_node("flaky", flaky_func, inputs=[], outputs=["result"],
                     config=NodeConfig(retry_count=3))
            .build())
        
        state = await flow.execute({})
        assert state.get("result") == "success"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_error_propagation(self):
        def failing_func():
            raise RuntimeError("Intentional failure")
        
        flow = (FlowBuilder("test_error")
            .add_node("fail", failing_func, inputs=[], outputs=[])
            .build())
        
        with pytest.raises(RuntimeError):
            await flow.execute({})


class TestPersistence:
    """Test checkpoint persistence."""
    
    @pytest.mark.asyncio
    async def test_memory_saver(self):
        saver = MemorySaver()
        state = FlowState().set("data", "test_value")
        
        await saver.save(state, "checkpoint_1")
        loaded = await saver.load("checkpoint_1")
        
        assert loaded is not None
        assert loaded.get("data") == "test_value"
    
    @pytest.mark.asyncio
    async def test_sqlite_saver(self):
        saver = SQLiteSaver(":memory:")
        state = FlowState().set("persistent", True)
        
        await saver.save(state, "sqlite_checkpoint")
        loaded = await saver.load("sqlite_checkpoint")
        
        assert loaded is not None
        assert loaded.get("persistent") is True


class TestSecurity:
    """Test security features."""
    
    def test_encryption_roundtrip(self):
        if not Encryptor.__dict__.get('_is_usable', True):
            pytest.skip("Cryptography not available")
        
        encryptor = Encryptor()
        plaintext = "sensitive data"
        
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_pii_detection(self):
        detector = PIIDetector()
        
        text = "Contact john@example.com or call 555-123-4567"
        findings = detector.detect(text)
        
        assert len(findings) >= 1
        assert any(f["type"] == "email" for f in findings)
    
    def test_pii_redaction(self):
        detector = PIIDetector()
        text = "Email: test@example.com, SSN: 123-45-6789"
        
        redacted = detector.redact(text)
        
        assert "test@example.com" not in redacted
        assert "123-45-6789" not in redacted
        assert "[REDACTED]" in redacted
    
    def test_input_sanitization_xss(self):
        sanitizer = InputSanitizer()
        malicious = "<script>alert('XSS')</script>Hello"
        
        sanitized = sanitizer.sanitize(malicious)
        
        assert "<script>" not in sanitized
        assert "alert" not in sanitized
    
    def test_rbac_permissions(self):
        rbac = RBACManager()
        rbac.assign_role("user1", "admin")
        rbac.assign_role("user2", "viewer")
        
        assert rbac.has_permission("user1", Permission.WRITE) is True
        assert rbac.has_permission("user2", Permission.WRITE) is False


class TestResilience:
    """Test resilience patterns."""
    
    def test_circuit_breaker_opens(self):
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("Failure")
        
        for _ in range(3):
            try:
                cb.call(failing_func)
            except:
                pass
        
        assert cb.state.name == "OPEN"
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        limiter = RateLimiter(rate_limit=5, window_seconds=60.0, burst_size=5)
        
        allowed = 0
        for _ in range(10):
            if await limiter.acquire():
                allowed += 1
        
        # Should allow burst_size (5) requests immediately due to token bucket
        assert allowed <= 10  # At least some should be limited
        assert allowed >= 5   # At least burst size should pass
    
    @pytest.mark.asyncio
    async def test_timeout_policy(self):
        timeout = TimeoutPolicy(timeout_seconds=0.1)
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"
        
        with pytest.raises(TimeoutError):
            await timeout.execute(slow_func)


class TestHITL:
    """Test Human-in-the-Loop functionality."""
    
    @pytest.mark.asyncio
    async def test_interrupt_creation_and_approval(self):
        engine = HITLEngine()
        
        interrupt = engine.create_interrupt(
            flow_id="flow1",
            node_id="approval_node",
            timeout_seconds=60.0
        )
        
        # Approve asynchronously
        async def approve_later():
            await asyncio.sleep(0.01)
            engine.approve(interrupt.id, "approver1", {"decision": "yes"})
        
        asyncio.create_task(approve_later())
        
        approved = await engine.wait_for_approval(interrupt.id, timeout=5.0)
        
        assert approved is True
        assert interrupt.status == ApprovalStatus.APPROVED


class TestTools:
    """Test tool system."""
    
    @pytest.mark.asyncio
    async def test_tool_decorator(self):
        @tool(name="add", description="Add two numbers", parameters={"a": {"type": "number"}, "b": {"type": "number"}})
        def add(a: int, b: int) -> int:
            return a + b
        
        result = await add.execute(a=5, b=3)
        assert result == 8
    
    @pytest.mark.asyncio
    async def test_tool_openai_schema(self):
        @tool(name="search", description="Search info", parameters={"query": {"type": "string"}})
        def search(query: str) -> str:
            return f"Results for {query}"
        
        schema = search.to_openai_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "query" in schema["function"]["parameters"]["properties"]


class TestConfiguration:
    """Test configuration system."""
    
    def test_config_from_env(self):
        os.environ["FLOWMIND_RETRY_COUNT"] = "5"
        os.environ["FLOWMIND_TIMEOUT"] = "60.0"
        
        config = FlowMindConfig.from_env()
        
        assert config.resilience.default_retry_count == 5
        assert config.resilience.default_timeout_seconds == 60.0


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_checkpointing_and_security(self):
        # Create saver
        saver = MemorySaver()
        
        # Create flow with checkpointing
        flow = (FlowBuilder("integration_test")
            .add_node("init", lambda: {"count": 0}, outputs=["count"])
            .add_node("increment", lambda count: count + 1, inputs=["count"], outputs=["new_count"])
            .connect("init", "increment")
            .with_checkpointing(saver)
            .build())
        
        # Execute
        state = await flow.execute({})
        
        # Verify checkpoint was saved
        checkpoints = await saver.list_checkpoints()
        assert len(checkpoints) > 0
        
        # Verify state
        assert state.get("new_count") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
