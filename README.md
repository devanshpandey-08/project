# 🛡️ AegisFlow v1.0.1 "True North"

**The Production-Grade AI Orchestration Framework for Enterprise.**

[![PyPI version](https://badge.fury.io/py/aegisflow.svg)](https://badge.fury.io/py/aegisflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Security Status](https://img.shields.io/badge/security-AES--256--GCM-green)](https://github.com/aegisflow/aegisflow/security)

> **Stop gluing mutable dictionaries together.** Start building immutable, auditable, and secure AI workflows.
> AegisFlow replaces the complexity of LangChain/LangGraph with a unified, type-safe engine designed for regulated industries (Finance, Healthcare, Legal).

---

## 🚀 Why AegisFlow?

If you are moving from LangChain, LangGraph, or CrewAI, you know the pain: mutable state causing race conditions, security as an afterthought, and debugging that requires external paid tools.

| Feature | LangChain / LangGraph | AegisFlow v1.0.1 |
| :--- | :--- | :--- |
| **State Management** | Mutable `dict` (Race conditions possible) | **Immutable Copy-on-Write** (Mathematically safe) |
| **Security** | External plugins / Manual implementation | **Native Core** (AES-256, PII Redaction, RBAC) |
| **Debugging** | LangSmith (Paid at scale) | **Built-in Time-Travel Replay** (Free & Local) |
| **Human-in-the-Loop** | `interrupt()` (Manual resume logic) | **Structured `ApprovalPattern`** with RBAC |
| **Concurrency** | Opt-in Async (`ainvoke`) | **Native Parallel Engine** (True async fan-out/fan-in) |
| **Compliance** | You build it | **SOC2/HIPAA Ready** (Audit Ledger included) |

---

## 📦 Installation

```bash
pip install aegisflow
```

*Requires Python 3.9+. For enterprise deployment, see our [Docker & Kubernetes Guides](./docs/deployment.md).*

---

## 🏁 Quick Start: Your First Secure Flow

In 20 lines of code, build a workflow that fetches data, auto-redacts PII, enforces role-based approval, and logs every step to an immutable ledger.

```python
import asyncio
from aegisflow import FlowBuilder, Tool, RBACRole, ApprovalPattern, Config

# 1. Define Type-Safe Tools
@Tool(name="fetch_user", parameters={"user_id": {"type": "string"}})
def fetch_user(user_id: str) -> dict:
    # Simulating DB fetch with sensitive data
    return {"id": user_id, "ssn": "123-45-6789", "risk_score": 0.9}

@Tool(name="redact_pii", parameters={"data": {"type": "object"}})
def redact_pii(data: dict) -> dict:
    # AegisFlow auto-detects PII, but explicit redaction is safe
    return {"id": data["id"], "ssn": "[REDACTED]", "risk_score": data["risk_score"]}

# 2. Build the Flow with Security & Resilience
flow = (FlowBuilder("secure_onboarding")
    .add_node("fetch", fetch_user, outputs=["user_data"])
    
    # Auto-encrypt state for this node
    .add_node("sanitize", redact_pii, inputs=["user_data"], 
              config={"encrypt_state": True})
    
    # Human Loop: Only triggers if risk > 0.8, requires 'manager' role
    .add_interrupt("manual_review", 
                   condition=lambda out: out.get("risk_score", 0) > 0.8,
                   pattern=ApprovalPattern.REQUIRED,
                   required_role=RBACRole(name="manager"))
    
    .add_node("finalize", lambda d: {"status": "approved", **d})
    .connect("fetch", "sanitize")
    .connect("sanitize", "manual_review")
    .connect("manual_review", "finalize")
    .build())

# 3. Execute with Audit Trail
async def main():
    result = await flow.execute(
        inputs={"user_id": "u_123"},
        trace_id="audit_2026_001" # Unique ID for compliance tracking
    )
    print(result.final_state)
    # Output: {'status': 'approved', 'ssn': '[REDACTED]'}

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🛡️ Security First: Built-In, Not Bolted-On

AegisFlow was born from the need for **compliance-ready AI**. We don't just process tokens; we protect data.

### 🔒 Automatic PII Redaction
The engine scans every state transition. If it detects SSNs, Credit Cards, or Emails, it redacts them *before* logging or storing.

```python
# Config enabled by default in production
config = Config(security={"pii_redaction": True})

input_data = {"credit_card": "4532-1234-5678-9012"}
# Internal State automatically becomes: {"credit_card": "[REDACTED_CC]"}
```

### 🔐 AES-256-GCM Encryption
Sensitive state nodes can be encrypted at rest. Keys are managed via environment variables or cloud KMS.

```python
.add_node("process_sensitive", func, config={"encrypt_state": True})
```

### 👮 Role-Based Access Control (RBAC)
Restrict node execution or approval rights to specific roles.

```python
# Only admins can execute this deletion node
.add_node("delete_db", delete_func, required_role=RBACRole.ADMIN)
```

### 📜 Immutable Audit Ledger
Every execution writes to a cryptographic ledger. You cannot alter history. Perfect for SOC2/HIPAA audits.

```python
from aegisflow import AuditLogger
logger = AuditLogger()
logs = logger.get_trace("audit_2026_001") # Returns signed, tamper-proof JSON
```

---

## 🧠 Advanced Patterns

### ⚡ True Parallel Execution
Unlike sequential chains, AegisFlow branches run in parallel with automatic state merging.

```python
flow = (FlowBuilder("research")
    .add_node("google", search_tool)
    .add_node("arxiv", search_tool)
    .connect("start", ["google", "arxiv"]) # Fan-out
    .connect(["google", "arxiv"], "synthesize") # Fan-in
    .build())
```

### ⏳ Time-Travel Debugging
Did your flow fail at step 7? Rewind and replay from step 6 with fixed inputs. No need to re-run the whole chain.

```python
checkpoint = flow.storage.get_checkpoint("cp_abc123")
new_result = await flow.replay(
    from_checkpoint=checkpoint,
    overrides={"step_6_input": {"fixed_value": True}}
)
```

### 🤝 Complex Human-in-the-Loop
Handle approvals, corrections, and multi-party sign-offs with structured patterns.

```python
.add_interrupt("legal_review", pattern=ApprovalPattern.UNANIMOUS, required_roles=["legal", "compliance"])
```

---

## 🧪 Testing & Reliability

Don't mock everything. AegisFlow allows deterministic testing of real flows with built-in chaos engineering support.

```python
from aegisflow.testing import FlowTester

tester = FlowTester(flow)

# Test happy path
assert tester.run(inputs={"user_id": "safe_user"}).status == "approved"

# Test security bypass attempt
try:
    tester.run(inputs={"payload": "<script>alert(1)</script>"})
except SecurityViolationError:
    print("XSS blocked successfully!")
```

*Run our full test suite:* `pytest tests/ -v` (Includes chaos, security fuzzing, and integration tests).

---

## 📚 Documentation

Ready to go deeper? Explore our comprehensive guides:

*   **[Getting Started](./docs/getting-started.md)**: Installation, Hello World, and Configuration.
*   **[Architecture Deep Dive](./docs/architecture.md)**: How Copy-on-Write State and the Async Engine work.
*   **[Security Whitepaper](./docs/security.md)**: Threat model, encryption standards, and compliance mappings (SOC2, HIPAA, GDPR).
*   **[API Reference](./docs/api/)**: Full auto-generated API documentation.
*   **[Deployment Guide](./docs/deployment.md)**: Docker, Kubernetes, and Cloud Formation templates.

---

## 🔄 Migration Guide (LangChain → AegisFlow)

| Task | LangChain Code | AegisFlow Code |
| :--- | :--- | :--- |
| **Define State** | `class State(TypedDict): ...` | `FlowState` (Automatic & Immutable) |
| **Add Retry** | `retryable_decorator` | `.add_node(..., config={"retry": 3})` |
| **Human Loop** | `interrupt()` + manual state mgmt | `.add_interrupt(..., pattern=ApprovalPattern)` |
| **Secure Data** | Manual filters | `config={"encrypt_state": True}` |
| **Debug** | `print(state)` or LangSmith UI | `flow.replay(checkpoint_id)` |

---

## 🤝 Community & Support

*   **GitHub Issues**: Report bugs or request features.
*   **Discord**: Join 1,000+ engineers building secure AI.
*   **Enterprise Support**: Contact us for SLA-backed support and custom compliance features.

**AegisFlow** is released under the MIT License. Built for developers who demand security, scalability, and sanity.

🌟 **Star us on GitHub** to stay updated on v1.1.0 (Multi-Agent Swarms & Quantum-Resistant Crypto).
