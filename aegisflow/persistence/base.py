from abc import ABC, abstractmethod
from typing import Any, Optional
class Checkpointer(ABC):
    @abstractmethod
    async def save(self, checkpoint_id: str, state: dict) -> None: pass
    @abstractmethod
    async def load(self, checkpoint_id: str) -> Optional[dict]: pass
