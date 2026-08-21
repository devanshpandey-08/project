"""Persistence layer with SQLite backend for checkpointing."""
import asyncio
import json
import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import threading

from flomind.core.state import FlowState


class CheckpointSaver:
    """Base class for checkpoint persistence."""
    
    async def save(self, state: FlowState, checkpoint_id: str) -> bool:
        raise NotImplementedError
    
    async def load(self, checkpoint_id: str) -> Optional[FlowState]:
        raise NotImplementedError
    
    async def list_checkpoints(self) -> List[str]:
        raise NotImplementedError
    
    async def delete(self, checkpoint_id: str) -> bool:
        raise NotImplementedError


class MemorySaver(CheckpointSaver):
    """In-memory checkpoint storage for testing."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, state: FlowState, checkpoint_id: str) -> bool:
        async with self._lock:
            self._cache[checkpoint_id] = {
                "state": state.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return True
    
    async def load(self, checkpoint_id: str) -> Optional[FlowState]:
        data = self._cache.get(checkpoint_id)
        if data:
            return FlowState.from_dict(data["state"])
        return None
    
    async def list_checkpoints(self) -> List[str]:
        return list(self._cache.keys())
    
    async def delete(self, checkpoint_id: str) -> bool:
        if checkpoint_id in self._cache:
            del self._cache[checkpoint_id]
            return True
        return False


class SQLiteSaver(CheckpointSaver):
    """SQLite-based checkpoint persistence with WAL mode for concurrency."""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = asyncio.Lock()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn
    
    def _init_db(self):
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                state_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_id ON checkpoints(id)")
        conn.commit()
    
    async def save(self, state: FlowState, checkpoint_id: str) -> bool:
        async with self._lock:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO checkpoints (id, state_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (checkpoint_id, json.dumps(state.to_dict()), now, now))
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to save checkpoint: {e}")
    
    async def load(self, checkpoint_id: str) -> Optional[FlowState]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT state_data FROM checkpoints WHERE id = ?",
            (checkpoint_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return FlowState.from_dict(json.loads(row[0]))
        return None
    
    async def list_checkpoints(self) -> List[str]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT id FROM checkpoints ORDER BY updated_at DESC")
        return [row[0] for row in cursor.fetchall()]
    
    async def delete(self, checkpoint_id: str) -> bool:
        async with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE id = ?",
                (checkpoint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
