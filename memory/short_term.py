"""
This module contains code to manage short term memory using redis

Requirement:
    Needs a redis server be running
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from core.config import REDIS_URL
from langgraph.checkpoint.redis.aio import AsyncRedisSaver


REDIS_URL = REDIS_URL


# NOTE: asynccontextmanager is decorated on definition that would run multiple async threads
# and called by asyncio.run()
@asynccontextmanager
async def get_short_term_memory() -> AsyncGenerator[AsyncRedisSaver, None]:
    """
    Returns an async Redis checkpointer for LangGraph.
    Use as a context manager:

    async with get_short_term_memory() as checkpointer:
        graph.compile(checkpointer=checkpointer)
    """
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
        yield checkpointer
