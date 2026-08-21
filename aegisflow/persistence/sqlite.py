import aiosqlite, json
from aegisflow.persistence.base import Checkpointer
class SQLiteSaver(Checkpointer):
    def __init__(self, db_path: str = "checkpoints.db"):
        self.db_path = db_path
    async def save(self, checkpoint_id: str, state: dict) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS checkpoints (id TEXT PRIMARY KEY, state TEXT)")
            await db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?, ?)", (checkpoint_id, json.dumps(state)))
            await db.commit()
    async def load(self, checkpoint_id: str) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT state FROM checkpoints WHERE id=?", (checkpoint_id,)) as cursor:
                row = await cursor.fetchone()
                return json.loads(row[0]) if row else None
