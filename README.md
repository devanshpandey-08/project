# FlowMind - The Next Generation AI Orchestration Framework

**FlowMind replaces LangChain and LangGraph with a unified, type-safe, and performant framework for building AI applications.**

## Why FlowMind?

LangChain and LangGraph have served the community well, but they suffer from:
- **Complexity**: Too many abstractions (Chains, Graphs, Agents, Tools, Memory)
- **Performance**: Heavy overhead and slow execution
- **Type Safety**: Poor typing leads to runtime errors
- **Observability**: Limited built-in monitoring

FlowMind solves these problems with:

### 1. Unified Flow Model
One primitive (`Flow`) replaces both Chains and Graphs. Everything is a flow.

### 2. Type-Safe State Management
Strongly-typed `FlowState` ensures data flows correctly through your application.

### 3. Built-In Observability
Tracing, metrics, and streaming are first-class citizens, not afterthoughts.

### 4. Resilience Patterns
Retry, timeout, and circuit breaker policies are built in.

### 5. Multi-Agent Teams
Coordinate multiple specialized agents with simple APIs.

## Installation

```bash
pip install flomind
```

## Quick Start

### Basic Flow

```python
import asyncio
from flomind import create_flow, FlowState

# Create a flow
flow = create_flow("hello_flow")

# Add nodes
@flow.add_node("greet")
async def greet(state: FlowState):
    name = state.get("name", "World")
    return f"Hello, {name}!"

@flow.add_node("respond")
async def respond(state: FlowState):
    greeting = state.outputs["greet"]
    return f"Response: {greeting}"

# Connect nodes
flow.add_edge("greet", "respond")
flow.set_exit_points("respond")

# Run
async def main():
    result = await flow.run(FlowState(inputs={"name": "FlowMind"}))
    print(result.outputs)

asyncio.run(main())
```

### Agent with Tools

```python
from flomind import Agent, Tool, tool

@tool
async def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

agent = Agent.create(
    name="researcher",
    tools=[search],
    system_prompt="You are a helpful researcher."
)

result = await agent.run("Find information about quantum computing")
print(result.output)
```

### Multi-Agent Team

```python
from flomind import AgentTeam, Agent, Role

team = AgentTeam.create("content_team")

team.add_agent(Agent.create("manager", role=Role.MANAGER))
team.add_agent(Agent.create("writer", role=Role.WRITER))
team.add_agent(Agent.create("reviewer", role=Role.REVIEWER))

result = await team.run("Write a blog post about AI")
print(result.results)
```

### Workflow Composition

```python
from flomind import Sequential, Parallel, Conditional, Loop

# Sequential execution
pipeline = Sequential(step1, step2, step3)

# Parallel execution
parallel = Parallel(task_a, task_b, task_c)

# Conditional branching
branch = Conditional(
    condition=lambda s: s.get("flag"),
    then_branch=if_true_flow,
    else_branch=if_false_flow
)

# Loop until condition met
loop = Loop(
    body=process_step,
    until=lambda s: s.get("done", False)
)
```

## Architecture

```
flomind/
├── core/           # Flow, Node, Edge, State
├── agents/         # Agent, Team
├── tools/          # Tool system
├── memory/         # Short/Long term memory
├── workflows/      # Workflow composition
├── policies/       # Retry, Timeout, Circuit Breaker
├── streaming/      # Event streaming
├── observability/  # Tracing, Metrics
├── vector/         # Vector store abstraction
└── llm/            # LLM provider abstraction
```

## Key Concepts

### Flow
A directed graph of nodes that defines execution workflow. Replaces both Chains and Graphs.

### Node
An execution unit that receives state, performs computation, and returns results.

### State
Type-safe container for data flowing through the system.

### Agent
Autonomous entity that can use tools, maintain memory, and complete tasks.

### Team
Collection of agents working together with coordination strategies.

### Policy
Resilience patterns (retry, timeout, circuit breaker) for robust execution.

## Comparison with LangChain/LangGraph

| Feature | LangChain/LangGraph | FlowMind |
|---------|---------------------|----------|
| Core Primitive | Chain + Graph | Flow |
| Type Safety | Partial | Full |
| State Management | Dict-based | Typed State |
| Observability | External | Built-in |
| Streaming | Limited | First-class |
| Multi-Agent | Complex | Simple |
| Resilience | Manual | Built-in |
| Performance | Heavy | Optimized |

## License

MIT License

## Contributing

Contributions welcome! See CONTRIBUTING.md for guidelines.
