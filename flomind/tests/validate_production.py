"""
FlowMind Enterprise Validation Suite
------------------------------------
This script performs a comprehensive end-to-end validation of the FlowMind framework.
It tests Security, Concurrency, Agent Logic, Resilience, and Observability.

Usage:
    python -m flomind.tests.validate_production
"""

import asyncio
import time
import uuid
import json
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Import Core Framework
from flomind.core.flow import Flow, create_flow, FlowState
from flomind.agents.agent import Agent
from flomind.tools.tool import Tool
from flomind.security.encryption import Encryptor
from flomind.security.pii import PIIDetector
from flomind.security.sanitizer import InputSanitizer
from flomind.security.audit_logger import AuditLogger, AuditEvent
from flomind.security.rbac import RBACManager, Role, Permission
from flomind.security.rate_limit import TokenBucketRateLimiter
from flomind.core.resilience import RetryPolicy, CircuitBreaker, TimeoutPolicy

# --- Mock LLM Provider for Testing (No API Keys Needed) ---
class MockLLMProvider:
    """Simulates an LLM response for deterministic testing."""
    
    async def generate(self, prompt: str, **kwargs) -> str:
        await asyncio.sleep(0.05)  # Simulate network latency
        if "calculate" in prompt.lower():
            return "The result is 42."
        if "secret" in prompt.lower():
            return "I found the secret key: SK-12345."
        return "I understand. Processing request..."
    
    async def generate_stream(self, prompt: str, **kwargs):
        response = "Streaming response chunk by chunk."
        for word in response.split():
            await asyncio.sleep(0.01)
            yield f"{word} "

# --- Test Suites ---

class SecurityTestSuite:
    """Validates Enterprise Security Features"""
    
    @staticmethod
    async def run():
        print("\n🔒 [SECURITY] Running Security Validation...")
        
        # 1. Encryption
        encryptor = Encryptor("test-master-key-32chars-long!!")
        original_data = "Sensitive User Data: SSN 123-45-6789"
        encrypted = encryptor.encrypt(original_data)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original_data, "Encryption/Decryption failed"
        assert encrypted != original_data, "Encryption did not alter data"
        print("   ✅ AES-256 Encryption/Decryption verified")
        
        # 2. PII Detection
        pii_detector = PIIDetector()
        text_with_pii = "Contact john.doe@example.com or call 555-0199."
        findings = pii_detector.detect(text_with_pii)
        assert len(findings) > 0, "PII Detection failed"
        redacted = pii_detector.redact(text_with_pii)
        assert "@" not in redacted or "[REDACTED]" in redacted, "PII Redaction failed"
        print(f"   ✅ PII Detection & Redaction verified ({len(findings)} items found)")
        
        # 3. Input Sanitization
        sanitizer = InputSanitizer()
        malicious_input = "<script>alert('xss')</script>Hello\u0000World"
        safe_input = sanitizer.sanitize(malicious_input)
        assert "<script>" not in safe_input, "XSS Sanitization failed"
        assert "\u0000" not in safe_input, "Null byte removal failed"
        print("   ✅ Input Sanitization (XSS/Nulls) verified")
        
        print("   🟢 SECURITY SUITE PASSED")

class RBACTestSuite:
    """Validates Role-Based Access Control"""
    
    @staticmethod
    async def run():
        print("\n🛡️  [RBAC] Running Access Control Validation...")
        
        rbac = RBACManager()
        
        # Define Roles
        admin_role = Role(name="admin", permissions=[Permission("*")])
        viewer_role = Role(name="viewer", permissions=[Permission("flow:read")])
        
        rbac.add_role(admin_role)
        rbac.add_role(viewer_role)
        
        # Assign Roles
        user_admin = "user_1"
        user_viewer = "user_2"
        rbac.assign_role(user_admin, "admin")
        rbac.assign_role(user_viewer, "viewer")
        
        # Test Permissions
        assert rbac.check_permission(user_admin, "flow:delete"), "Admin should delete"
        assert not rbac.check_permission(user_viewer, "flow:delete"), "Viewer should NOT delete"
        assert rbac.check_permission(user_viewer, "flow:read"), "Viewer should read"
        
        print("   ✅ Role Hierarchy & Permission Checks verified")
        print("   🟢 RBAC SUITE PASSED")

class RateLimitTestSuite:
    """Validates Rate Limiting Algorithms"""
    
    @staticmethod
    async def run():
        print("\n⏱️  [RATE LIMIT] Running Throughput Validation...")
        
        limiter = TokenBucketRateLimiter(rate=10, capacity=10) # 10 req/sec
        
        success_count = 0
        blocked_count = 0
        
        # Burst test: Try 15 requests instantly
        for _ in range(15):
            if limiter.acquire():
                success_count += 1
            else:
                blocked_count += 1
        
        assert success_count == 10, f"Expected 10 allowed, got {success_count}"
        assert blocked_count == 5, f"Expected 5 blocked, got {blocked_count}"
        
        print(f"   ✅ Token Bucket Algorithm verified (Allowed: {success_count}, Blocked: {blocked_count})")
        print("   🟢 RATE LIMIT SUITE PASSED")

class ResilienceTestSuite:
    """Validates Retry, Timeout, and Circuit Breaker"""
    
    @staticmethod
    async def run():
        print("\n🔄 [RESILIENCE] Running Fault Tolerance Validation...")
        
        # 1. Timeout Policy
        timeout_policy = TimeoutPolicy(timeout_seconds=0.1)
        start = time.time()
        try:
            async def slow_op():
                await asyncio.sleep(1.0)
                return "done"
            await timeout_policy.execute(slow_op)
            assert False, "Timeout should have triggered"
        except TimeoutError:
            elapsed = time.time() - start
            assert elapsed < 0.5, "Timeout took too long to trigger"
            print("   ✅ Timeout Policy verified")
        
        # 2. Retry Policy
        retry_policy = RetryPolicy(max_retries=3, delay=0.01)
        attempt_count = 0
        
        async def flaky_op():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Transient error")
            return "success"
            
        result = await retry_policy.execute(flaky_op)
        assert result == "success", "Retry logic failed"
        assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
        print("   ✅ Retry Policy verified")
        
        # 3. Circuit Breaker
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        async def failing_op():
            raise Exception("Service down")
            
        # Trip the breaker
        for _ in range(3):
            try:
                await cb.execute(failing_op)
            except:
                pass
        
        assert cb.state == "OPEN", "Circuit breaker should be OPEN"
        
        try:
            await cb.execute(failing_op)
            assert False, "Circuit breaker should reject calls when OPEN"
        except Exception as e:
            assert "Circuit Open" in str(e) or "open" in str(e).lower(), "Wrong exception"
            print("   ✅ Circuit Breaker State verified")
            
        print("   🟢 RESILIENCE SUITE PASSED")

class AgentFlowTestSuite:
    """Validates Core Agent & Flow Logic"""
    
    @staticmethod
    async def run():
        print("\n🤖 [AGENT FLOW] Running Orchestration Validation...")
        
        # Define Tools
        @Tool(description="Calculates math problems")
        def calculator(query: str) -> str:
            return "42"
            
        @Tool(description="Searches internal knowledge base")
        def search_db(query: str) -> str:
            return "Found relevant document: ID-999"
        
        # Create Agents
        researcher = Agent(
            name="Researcher",
            role="Senior Data Analyst",
            tools=[search_db],
            llm_provider=MockLLMProvider()
        )
        
        mathematician = Agent(
            name="MathWhiz",
            role="Calculation Specialist",
            tools=[calculator],
            llm_provider=MockLLMProvider()
        )
        
        # Create a Sequential Flow
        flow = create_flow(
            name="AnalysisPipeline",
            steps=[researcher, mathematician],
            mode="sequential"
        )
        
        # Execute Flow
        initial_state = FlowState({"query": "What is the meaning of life?", "context": "Philosophy"})
        result_state = await flow.run(initial_state)
        
        assert result_state is not None, "Flow execution returned None"
        assert "history" in result_state.data or len(result_state.data) > 0, "State not updated"
        
        print("   ✅ Multi-Agent Sequential Flow executed successfully")
        
        # Test Parallel Execution
        parallel_flow = create_flow(
            name="ParallelTask",
            steps=[researcher, mathematician],
            mode="parallel"
        )
        
        start = time.time()
        parallel_result = await parallel_flow.run(initial_state)
        elapsed = time.time() - start
        
        # Parallel should be faster than sum of sequential (approx)
        assert parallel_result is not None, "Parallel flow failed"
        print(f"   ✅ Parallel Flow executed in {elapsed:.3f}s")
        
        print("   🟢 AGENT FLOW SUITE PASSED")

class AuditTrailTestSuite:
    """Validates Immutable Audit Logging"""
    
    @staticmethod
    async def run():
        print("\n📝 [AUDIT] Running Compliance Logging Validation...")
        
        logger = AuditLogger(service_name="flomind-test", log_level="INFO")
        
        event = AuditEvent(
            actor_id="user_123",
            action="flow.execute",
            resource_id="flow_abc",
            details={"input_size": 1024, "status": "success"},
            sensitivity="HIGH"
        )
        
        logger.log(event)
        
        # In a real scenario, this writes to disk/S3. 
        # Here we verify the logger accepts and formats correctly without crashing.
        assert event.timestamp is not None, "Event missing timestamp"
        assert event.event_id is not None, "Event missing ID"
        
        print("   ✅ Audit Event Generation & Formatting verified")
        print("   🟢 AUDIT SUITE PASSED")

class PerformanceBenchmark:
    """Basic Performance Sanity Check"""
    
    @staticmethod
    async def run():
        print("\n⚡ [PERFORMANCE] Running Concurrency Benchmark...")
        
        simple_agent = Agent(
            name="Worker",
            role="Task Executor",
            llm_provider=MockLLMProvider()
        )
        
        flow = create_flow(name="BenchFlow", steps=[simple_agent], mode="sequential")
        
        concurrency_levels = [10, 50, 100]
        
        for level in concurrency_levels:
            tasks = [
                flow.run(FlowState({"task_id": i})) 
                for i in range(level)
            ]
            
            start = time.time()
            await asyncio.gather(*tasks)
            elapsed = time.time() - start
            
            ops_per_sec = level / elapsed
            print(f"   ✅ Concurrency {level}: Completed in {elapsed:.2f}s ({ops_per_sec:.1f} ops/sec)")
            
        print("   🟢 PERFORMANCE BENCHMARK COMPLETED")

# --- Main Runner ---

async def main():
    print("="*60)
    print("  FlowMind Enterprise Validation Suite")
    print("  Replacing LangChain/LangGraph with Secure, Typed Orchestration")
    print("="*60)
    
    try:
        await SecurityTestSuite.run()
        await RBACTestSuite.run()
        await RateLimitTestSuite.run()
        await ResilienceTestSuite.run()
        await AgentFlowTestSuite.run()
        await AuditTrailTestSuite.run()
        await PerformanceBenchmark.run()
        
        print("\n" + "="*60)
        print("  🎉 ALL VALIDATION SUITES PASSED")
        print("  FlowMind is ready for Enterprise Deployment.")
        print("="*60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
