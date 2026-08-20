"""
Comprehensive Production Test Suite for FlowMind.

Tests cover:
- Core flow execution
- Security (encryption, PII, sanitization)
- RBAC and rate limiting
- Audit logging
- Agents and teams
- Tools system
- Resilience patterns
- Observability
"""

import pytest
import asyncio
import time
from typing import Any, Dict

# Import all components
from flomind import (
    Flow, FlowState, NodeType, FlowExecutor,
    Agent, Team, Tool, ToolRegistry,
    Encryptor, PIIDetector, InputSanitizer,
    AuditLogger, AuditEventType,
    RBACManager, Role, Permission,
    RateLimiter, RateLimitPolicy,
    RetryPolicy, TimeoutPolicy, CircuitBreaker,
    Tracer, MetricsCollector,
    create_flow, create_agent, create_team
)


class TestCoreFlow:
    """Test core flow functionality."""
    
    def test_flow_creation(self):
        """Test basic flow creation."""
        flow = Flow(name="test_flow")
        assert flow.name == "test_flow"
        assert flow.id is not None
        
    def test_flow_execution(self):
        """Test flow execution with nodes."""
        def process(state, **kwargs):
            return {"result": "processed"}
            
        flow = Flow(name="test")
        flow.add_node("start", NodeType.START, "Start")
        flow.add_node("process", NodeType.TASK, "Process", func=process)
        flow.add_node("end", NodeType.END, "End")
        flow.add_edge("start", "process")
        flow.add_edge("process", "end")
        
        result = flow.execute({})
        assert result.success is True
        assert result.trace_id != ""
        
    def test_flow_state_management(self):
        """Test type-safe state management."""
        state = FlowState()
        state.set("key1", "value1")
        state.update({"key2": "value2"})
        
        assert state.get("key1") == "value1"
        assert state.get("key2") == "value2"
        assert len(state.history) == 2


class TestSecurity:
    """Test security features."""
    
    def test_encryption_decryption(self):
        """Test AES-256-GCM encryption."""
        encryptor = Encryptor()
        plaintext = "Secret message for testing"
        
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        
        assert decrypted == plaintext
        assert ciphertext != plaintext
        
    def test_pii_detection(self):
        """Test PII detection."""
        detector = PIIDetector()
        
        text = "Contact john@example.com or call 555-123-4567"
        matches = detector.detect(text)
        
        assert len(matches) >= 1
        
    def test_pii_redaction(self):
        """Test PII redaction."""
        detector = PIIDetector()
        text = "Email: test@example.com, SSN: 123-45-6789"
        
        redacted = detector.redact(text)
        
        assert "test@example.com" not in redacted
        assert "123-45-6789" not in redacted
        
    def test_xss_sanitization(self):
        """Test XSS prevention."""
        sanitizer = InputSanitizer()
        
        malicious = '<script>alert("XSS")</script>Hello'
        sanitized = sanitizer.sanitize(malicious)
        
        assert "<script>" not in sanitized


class TestRBAC:
    """Test role-based access control."""
    
    def test_builtin_roles(self):
        """Test built-in system roles."""
        rbac = RBACManager()
        
        rbac.assign_role("user1", "admin")
        assert rbac.has_permission("user1", "flow:read")
        
    def test_permission_check(self):
        """Test permission checking."""
        rbac = RBACManager()
        rbac.assign_role("user1", "viewer")
        
        assert rbac.has_permission("user1", "flow:read")
        assert not rbac.has_permission("user1", "flow:delete")


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(RateLimitPolicy(burst_size=5))
        
        result, metadata = limiter.allow_request("test_user")
        assert result is True


class TestAuditLogging:
    """Test audit logging for compliance."""
    
    def test_audit_event_creation(self):
        """Test creating audit events."""
        logger = AuditLogger(mask_sensitive=False)
        
        event = logger.log(
            event_type=AuditEventType.FLOW_EXECUTION,
            action="execute",
            resource="flow",
            status="success",
            user_id="test_user"
        )
        
        assert event.event_id is not None
        assert event.user_id == "test_user"


class TestAgents:
    """Test agent functionality."""
    
    def test_agent_creation(self):
        """Test agent creation."""
        agent = Agent(name="TestAgent", role="assistant")
        
        assert agent.name == "TestAgent"


class TestTools:
    """Test tool system."""
    
    def test_tool_creation(self):
        """Test tool creation."""
        def my_func(x: int) -> int:
            return x * 2
            
        tool = Tool(name="doubler", description="Doubles a number", func=my_func)
        
        assert tool.name == "doubler"
        
    def test_tool_execution(self):
        """Test tool execution."""
        tool = Tool(name="adder", description="Adds numbers", func=lambda x, y: x + y)
        
        result = tool.execute(x=5, y=3)
        
        assert result.success is True
        assert result.output == 8


class TestResilience:
    """Test resilience patterns."""
    
    def test_retry_policy(self):
        """Test retry policy."""
        policy = RetryPolicy(max_retries=3, delay=0.1)
        
        assert policy.max_retries == 3
        
    def test_circuit_breaker(self):
        """Test circuit breaker."""
        cb = CircuitBreaker(failure_threshold=3)
        
        for _ in range(3):
            cb.record_failure()
            
        assert cb.state == "open"


class TestObservability:
    """Test tracing and metrics."""
    
    def test_tracer_spans(self):
        """Test distributed tracing."""
        tracer = Tracer()
        
        with tracer.trace("test_operation", key="value") as span:
            time.sleep(0.01)
            
        spans = tracer.export()
        
        assert len(spans) == 1
        
    def test_metrics_collection(self):
        """Test metrics collection."""
        metrics = MetricsCollector()
        
        metrics.increment("requests_total", method="GET")
        metrics.increment("requests_total", method="GET")
        
        assert metrics.get_counter("requests_total", method="GET") == 2.0


class TestFactoryFunctions:
    """Test factory functions."""
    
    def test_create_flow_factory(self):
        """Test flow factory function."""
        def process(state, **kwargs):
            return {"done": True}
            
        flow = create_flow(
            name="factory_flow",
            nodes={"process": process},
            edges=[("start", "process"), ("process", "end")]
        )
        
        assert flow.name == "factory_flow"
        
    def test_create_agent_factory(self):
        """Test agent factory function."""
        agent = create_agent(
            name="FactoryAgent",
            role="helper"
        )
        
        assert agent.name == "FactoryAgent"
        
    def test_create_team_factory(self):
        """Test team factory function."""
        agents = [create_agent(name=f"Agent{i}", role="worker") for i in range(2)]
        team = create_team(name="FactoryTeam", agents=agents)
        
        assert team.name == "FactoryTeam"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
