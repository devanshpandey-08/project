from aegisflow.persistence.base import Checkpointer
class MemorySaver(Checkpointer):
    def __init__(self): self._store = {}
    async def save(self, checkpoint_id: str, state: dict) -> None: self._store[checkpoint_id] = state
    async def load(self, checkpoint_id: str) -> dict: return self._store.get(checkpoint_id)
