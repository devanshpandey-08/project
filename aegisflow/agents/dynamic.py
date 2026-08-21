from enum import Enum
class AgentMode(Enum):
    CREATIVE = "creative"
    COMPLIANCE = "compliance"
class DynamicAgent:
    def __init__(self, name: str, mode: AgentMode = AgentMode.COMPLIANCE):
        self.name, self.mode = name, mode
    async def execute(self, task: str) -> str:
        if self.mode == AgentMode.CREATIVE:
            return f"[CREATIVE] Executing: {task}"
        else:
            return f"[COMPLIANCE] Secure execution: {task}"
