
import os
import asyncpg
from typing import Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, url: str = None):
        self.url = url or os.getenv("DATABASE_URL")
        if not self.url:
             # Fallback or error? Assuming user provides it as in previous steps
             pass
        self.pool = None

    async def connect(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.url)
            except Exception as e:
                logger.error(f"Failed to connect to DB: {e}")
                raise

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def fetch_one(self, query: str, *args) -> Optional[dict]:
        if not self.pool: await self.connect()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, *args)
            return dict(record) if record else None

    async def fetch_all(self, query: str, *args) -> List[dict]:
        if not self.pool: await self.connect()
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, *args)
            return [dict(r) for r in records]

    async def execute(self, query: str, *args) -> str:
        if not self.pool: await self.connect()
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

# Global instances can be managed by FastAPI lifecycle
db = Database()
