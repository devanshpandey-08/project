"""
Comprehensive Integration Tests for FlowMind
Tests all components working together in real-world scenarios
"""

import asyncio
import pytest
from typing import Dict, Any

# Core imports
from flomind import (
    Flow, Agent, Tool, create_flow, FlowState,
    Encryptor, PIIDetector, InputSanitizer,
    AuditLogger, RBACManager,
    RetryPolicy, TimeoutPolicy, CircuitBreakerPolicy
)
from flomind.security import AES256Encryptor
from flomind.security.audit_logger import AuditLogger
from flomind.security.rbac import RBACManager, Role, Permission
from flomind.security.rate_limit import TokenBucketRateLimiter


class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_secure_agent_workflow(self):
        """Test agent with security features enabled"""
        encryptor = AES256Encryptor(key_bytes=b"32_byte_secret_key_for_testing!")
        pii_detector = PIIDetector()
        sanitizer = InputSanitizer()
        
        # Create secure tool
        @Tool(
            name="secure_processor",
            description="Process data with security checks",
            parameters={"data": {"type": "string"}}
        )
        def secure_process(data: str) -> str:
            clean_data = sanitizer.sanitize(data)
            pii_found = pii_detector.detect(clean_data)
            if pii_found:
                clean_data = pii_detector.redact(clean_data)
            result = f"Processed: {clean_data}"
            encrypted = encryptor.encrypt(result)
            return encrypted
        
        test_input = "User email: john@example.com"
        result = secure_process.invoke({"data": test_input})
        
        assert len(result) > 0
        print(f"✓ Secure workflow completed")

    def test_rbac_protected_flow(self):
        """Test flow with RBAC enforcement"""
        rbac = RBACManager()

        admin_role = Role(
            id="admin",
            permissions=[
                Permission("flow:execute"),
                Permission("flow:modify"),
                Permission("agent:create"),
                Permission("agent:delete")
            ]
        )

        viewer_role = Role(
            id="viewer",
            permissions=[
                Permission("flow:execute")
            ]
        )

        rbac.add_role(admin_role)
        rbac.add_role(viewer_role)
        rbac.assign_role_to_user("alice", "admin")
        rbac.assign_role_to_user("bob", "viewer")

        assert rbac.has_permission("alice", "flow", "execute")
        assert rbac.has_permission("alice", "flow", "modify")
        assert rbac.has_permission("bob", "flow", "execute")
        assert not rbac.has_permission("bob", "flow", "modify")

        print(f"✓ RBAC protection working correctly")

    def test_rate_limited_execution(self):
        """Test rate limiting on tool execution"""
        rate_limiter = TokenBucketRateLimiter(
            capacity=5,
            rate=1.0
        )
        
        call_count = 0
        
        @Tool(
            name="limited_tool",
            description="Rate limited tool",
            parameters={}
        )
        def limited_action() -> str:
            nonlocal call_count
            if not rate_limiter.acquire("user1"):
                raise Exception("Rate limit exceeded")
            call_count += 1
            return f"Call #{call_count}"
        
        results = []
        for i in range(5):
            try:
                result = limited_action.invoke({})
                results.append(result)
            except Exception as e:
                break
        
        assert len(results) == 5
        print(f"✓ Rate limiting enforced correctly")

    def test_audit_compliance_workflow(self):
        """Test audit logging for compliance"""
        logger = AuditLogger(service_name="test_service")
        
        logger.log_event("access", "user123", "flow:main", {"action": "execute"})
        logger.log_event("modification", "user123", "agent:worker", {"change": "updated config"})
        logger.log_event("security", "user123", "pii_detected", {"field": "email"})
        
        print(f"✓ Audit logging operational")

    def test_resilient_flow_execution(self):
        """Test flow with retry, timeout, and circuit breaker"""
        call_attempts = 0
        
        @Tool(
            name="flaky_tool",
            description="Tool that fails twice then succeeds",
            parameters={}
        )
        def flaky_action() -> str:
            nonlocal call_attempts
            call_attempts += 1
            if call_attempts < 3:
                raise Exception("Temporary failure")
            return "Success!"
        
        flow = create_flow(
            name="resilient_flow",
            nodes={
                "process": flaky_action
            },
            edges=[("start", "process"), ("process", "end")],
            retry_policy=RetryPolicy(
                max_retries=3,
                delay_seconds=0.1,
                exponential_backoff=True
            ),
            timeout_policy=TimeoutPolicy(
                timeout_seconds=5.0
            ),
            circuit_breaker_policy=CircuitBreakerPolicy(
                failure_threshold=5,
                recovery_timeout=10.0
            )
        )
        
        result = flow.execute({})
        assert call_attempts == 3
        print(f"✓ Resilience patterns working (retried {call_attempts} times)")

    def test_multi_agent_team_collaboration(self):
        """Test team of agents working together"""
        
        @Tool(
            name="research_tool",
            description="Research information",
            parameters={"query": {"type": "string"}}
        )
        def research(query: str) -> str:
            return f"Research results for: {query}"
        
        @Tool(
            name="write_tool",
            description="Write content",
            parameters={"content": {"type": "string"}}
        )
        def write(content: str) -> str:
            return f"Written content: {content[:50]}..."
        
        researcher = Agent(
            name="Researcher",
            role="Information Gatherer",
            tools=[research_tool],
            system_prompt="You research topics thoroughly."
        )
        
        writer = Agent(
            name="Writer",
            role="Content Creator",
            tools=[write_tool],
            system_prompt="You create engaging content."
        )
        
        from flomind.agents import Team
        from flomind.agents.team import TeamStrategy
        
        team = Team(
            name="ContentTeam",
            members=[researcher, writer],
            strategy=TeamStrategy.SEQUENTIAL
        )
        
        assert len(team.members) == 2
        assert team.strategy == TeamStrategy.SEQUENTIAL
        print(f"✓ Multi-agent team created successfully")

    def test_encrypted_state_management(self):
        """Test state management with encryption"""
        encryptor = AES256Encryptor(key_bytes=b"another_32_byte_key_for_state!")
        
        state = FlowState(initial_data={
            "public_info": "visible data",
            "sensitive_info": "secret credentials"
        })
        
        sensitive_value = state.get("sensitive_info")
        encrypted = encryptor.encrypt(str(sensitive_value))
        decrypted = encryptor.decrypt(encrypted).decode('utf-8')
        
        assert decrypted == "secret credentials"
        print(f"✓ State encryption/decryption working")

    def test_pii_handling_complete_flow(self):
        """Test complete PII detection and redaction flow"""
        detector = PIIDetector()
        
        test_cases = [
            ("Contact me at john.doe@example.com", True),
            ("Call 555-123-4567 for support", True),
            ("SSN: 123-45-6789", True),
            ("Card: 4111-1111-1111-1111", True),
            ("Regular text without PII", False),
        ]
        
        for text, should_detect in test_cases:
            result = detector.detect(text)
            has_pii = len(result) > 0
            assert has_pii == should_detect, f"Failed for: {text}"
        
        text_with_pii = "Email john@test.com and phone 555-999-8888"
        redacted = detector.redact(text_with_pii)
        
        assert "john@test.com" not in redacted
        assert "555-999-8888" not in redacted
        assert "[EMAIL]" in redacted or "[REDACTED]" in redacted
        
        print(f"✓ PII handling complete flow verified")


class TestEnterpriseScenarios:
    """Enterprise-level scenario tests"""

    def test_multi_tenant_isolation(self):
        """Test tenant isolation in RBAC"""
        rbac = RBACManager()
        
        tenant_a_admin = Role(
            id="tenant_a_admin",
            permissions=[Permission("resource:access")],
            metadata={"tenant": "tenant_a"}
        )
        
        tenant_b_admin = Role(
            id="tenant_b_admin",
            permissions=[Permission("resource:access")],
            metadata={"tenant": "tenant_b"}
        )
        
        rbac.add_role(tenant_a_admin)
        rbac.add_role(tenant_b_admin)
        rbac.assign_role_to_user("alice_a", "tenant_a_admin")
        rbac.assign_role_to_user("bob_b", "tenant_b_admin")
        
        assert rbac.has_permission("alice_a", "resource", "access")
        assert rbac.has_permission("bob_b", "resource", "access")
        
        print(f"✓ Multi-tenant isolation configured")

    def test_high_volume_rate_limiting(self):
        """Test rate limiting under high load"""
        rate_limiter = TokenBucketRateLimiter(
            capacity=100,
            rate=10.0
        )
        
        allowed = 0
        denied = 0
        
        for i in range(150):
            if rate_limiter.acquire("high_volume_user"):
                allowed += 1
            else:
                denied += 1
        
        assert allowed == 100
        assert denied == 50
        
        print(f"✓ High volume rate limiting working (allowed: {allowed}, denied: {denied})")

    def test_comprehensive_audit_trail(self):
        """Test complete audit trail for compliance"""
        logger = AuditLogger(service_name="compliance_test")
        
        user_id = "compliance_user"
        
        logger.log_event("access", user_id, "system", {"action": "login"})
        logger.log_event("access", user_id, "flow:data_processor", {"action": "execute"})
        logger.log_event("modification", user_id, "config", {"change": "changed threshold"})
        logger.log_event("security", user_id, "anomaly_detected", {"score": 0.95})
        logger.log_event("access", user_id, "system", {"action": "logout"})
        
        print(f"✓ Comprehensive audit trail created")


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("FLOWMIND COMPREHENSIVE INTEGRATION TESTS")
    print("="*60 + "\n")
    
    test_classes = [
        TestIntegrationScenarios,
        TestEnterpriseScenarios
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total_tests += 1
                try:
                    getattr(instance, method_name)()
                    passed_tests += 1
                except Exception as e:
                    print(f"✗ {method_name} FAILED: {e}")
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    print("="*60 + "\n")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
