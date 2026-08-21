# 🛡️ AegisFlow v1.0.0

**Production-Grade AI Orchestration with Dual-Mode (Creative/Compliance)**

AegisFlow is a secure, type-safe, async-first AI orchestration framework that uniquely supports both:
- **Creative Mode**: Open-ended agentic workflows (like LangChain) for research, web browsing, and exploration
- **Compliance Mode**: Deterministic, audited, PII-redacted flows for enterprise/HIPAA/SOC2 use cases

---

## ⚡ Quick Start

```bash
pip install aegisflow
```

```python
from aegisflow import FlowBuilder, DynamicAgent, AgentMode, Tool, Encryptor

# 🔐 Security First - AES-256 Encryption
crypto = Encryptor()
encrypted = crypto.encrypt("sensitive_data")

# 🤖 Dual-Mode Agents
creative_agent = DynamicAgent("Researcher", mode=AgentMode.CREATIVE)
compliance_agent = DynamicAgent("Auditor", mode=AgentMode.COMPLIANCE)

# 🛠️ Type-Safe Tools
@Tool(name="search", description="Search the web")
def search(q: str): return f"Results for {q}"

# 🔄 Build Secure Flows
async def fetch(query: str): return {"data": f"Result: {query}"}

flow = (FlowBuilder("secure_flow")
    .add_node("fetch", fetch, inputs=["query"])
    .build())

import asyncio
result = asyncio.run(flow.execute({"query": "test"}))
```

---

## 🎯 When to Choose AegisFlow vs LangChain/LangGraph

| Use Case | Recommended Framework | Why |
|----------|---------------------|-----|
| **Consumer Chatbot** | LangChain | Maximum flexibility, creative freedom |
| **Open-Ended Research** | LangChain | Web browsing, autonomous agents |
| **Rapid Prototyping** | LangChain | Speed over strict auditability |
| **HIPAA/SOC2 Workflows** | **AegisFlow** ✅ | Built-in PII redaction, audit logs |
| **Financial Data Processing** | **AegisFlow** ✅ | AES-256 encryption, RBAC |
| **Healthcare Applications** | **AegisFlow** ✅ | Compliance-first architecture |
| **Enterprise Automation** | **AegisFlow** ✅ | Role-based access, immutable state |

**Rule of Thumb:**
- If hallucination is acceptable but data leaks aren't → **AegisFlow**
- If you need maximum creative freedom → **LangChain**

---

## 🔒 Security Features (Built-In, Not Plugins)

| Feature | Description |
|---------|-------------|
| **AES-256-GCM Encryption** | State encryption with persistent key management |
| **PII Detection & Redaction** | Auto-detects SSN, email, phone, credit cards (with homoglyph protection) |
| **RBAC** | Role-based access control with inheritance |
| **Immutable Audit Ledger** | Cryptographically-linked execution logs |
| **Input Sanitization** | XSS/injection prevention |

---

## 🏗️ Architecture Highlights

- **Immutable State**: Copy-on-write semantics prevent race conditions
- **Async-Native**: True parallel execution (not sequential like LangGraph default)
- **Type-Safe**: Full static typing with Pydantic validation
- **Dual-Mode**: Switch between Creative and Compliance modes per agent
- **Checkpointing**: SQLite/Redis/Memory savers with time-travel replay

---

## 📦 Installation

```bash
# Install from PyPI
pip install aegisflow

# Or from source
git clone https://github.com/yourorg/aegisflow.git
cd aegisflow && pip install -e ".[dev]"
```

---

## 🧪 Testing

```bash
pytest tests/ -v --cov=aegisflow
```

---

## 📚 Documentation

- [Getting Started](docs/getting_started.md)
- [Architecture Deep Dive](docs/architecture.md)
- [Security Whitepaper](docs/security.md)
- [Deployment Guide](docs/deployment.md)
- [API Reference](docs/api.md)

---

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guide](CONTRIBUTING.md).

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

---

**Built for enterprises that can't afford compromises between security and capability.**
