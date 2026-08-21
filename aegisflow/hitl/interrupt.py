import asyncio
from enum import Enum
class ApprovalPattern(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
class HumanInterrupt:
    def __init__(self, interrupt_id: str, description: str, pattern: ApprovalPattern = ApprovalPattern.REQUIRED):
        self.interrupt_id, self.description, self.pattern = interrupt_id, description, pattern
        self._event = asyncio.Event()
        self.response = None
    async def wait(self, timeout_seconds: float = 300.0) -> any:
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_seconds)
            return self.response
        except asyncio.TimeoutError:
            raise RuntimeError(f"Interrupt {self.interrupt_id} timed out")
    def resolve(self, response: any):
        self.response = response
        self._event.set()
