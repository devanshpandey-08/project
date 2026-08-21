"""
AegisFlow Dynamic Agent Core
Supports "Creative Mode" for open-ended, recursive, agentic behavior.
"""
from typing import List, Dict, Any, Optional, Callable
import asyncio
from dataclasses import dataclass
from enum import Enum

class AgentMode(Enum):
    CREATIVE = "creative"  # Unbounded, recursive, exploratory
    COMPLIANCE = "compliance"  # Deterministic, audited, strict

@dataclass
class ThoughtStep:
    thought: str
    action: str
    observation: Optional[str] = None

class DynamicAgent:
    """
    A recursive, self-correcting agent capable of open-ended tasks.
    Equivalent to LangChain's 'AgentExecutor' but with optional security guards.
    """
    
    def __init__(
        self, 
        name: str, 
        tools: List[Callable], 
        mode: AgentMode = AgentMode.CREATIVE,
        max_iterations: int = 10
    ):
        self.name = name
        self.tools = {t.__name__: t for t in tools}
        self.mode = mode
        self.max_iterations = max_iterations
        self.thought_history: List[ThoughtStep] = []

    async def plan(self, task: str, context: Dict[str, Any]) -> str:
        """
        Generates a high-level plan. In Creative Mode, this can be vague.
        In Compliance Mode, this must be a strict step-by-step graph.
        """
        if self.mode == AgentMode.COMPLIANCE:
            # In compliance mode, we delegate to the strict FlowBuilder
            return "Delegating to strict flow graph..."
        
        # Creative Mode: LLM generates flexible plan
        return f"Plan: 1. Search for '{task}'. 2. Analyze results. 3. Synthesize answer."

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        The ReAct loop: Thought -> Action -> Observation.
        """
        current_task = task
        iterations = 0
        
        while iterations < self.max_iterations:
            # 1. Think
            thought = await self._think(current_task, context)
            
            # 2. Decide Action
            action_name, action_input = await self._decide_action(thought)
            
            if action_name == "FINISH":
                return {"result": action_input, "history": self.thought_history}
            
            # 3. Execute Tool
            if action_name not in self.tools:
                raise ValueError(f"Unknown tool: {action_name}")
            
            observation = await self._call_tool(action_name, action_input)
            
            # 4. Record Step
            step = ThoughtStep(thought=thought, action=f"{action_name}({action_input})", observation=observation)
            self.thought_history.append(step)
            
            # 5. Self-Correct / Loop
            if self.mode == AgentMode.COMPLIANCE:
                # Strict validation before next loop
                if not self._validate_observation(observation):
                    raise SecurityError("Observation failed compliance check")
            
            current_task = f"Previous result: {observation}. Next step to finish: {task}"
            iterations += 1
            
        raise TimeoutError(f"Agent {self.name} exceeded max iterations ({self.max_iterations})")

    async def _think(self, task: str, context: Dict[str, Any]) -> str:
        # Placeholder for LLM call - In production, this calls your LLM provider
        return f"Analyzing task: {task}"

    async def _decide_action(self, thought: str) -> tuple:
        # Placeholder for LLM decision
        # Returns (tool_name, input_dict) or ("FINISH", final_answer)
        return ("FINISH", "Final Answer based on thought.")

    async def _call_tool(self, name: str, input_data: Any) -> str:
        tool = self.tools[name]
        if asyncio.iscoroutinefunction(tool):
            return await tool(input_data)
        return tool(input_data)

    def _validate_observation(self, obs: str) -> bool:
        # PII check, toxicity check, etc.
        return True

class SecurityError(Exception):
    pass
