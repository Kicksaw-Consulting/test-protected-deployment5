from contextlib import asynccontextmanager
from typing import AsyncIterator

from httpx import AsyncClient, AsyncHTTPTransport, Timeout


@asynccontextmanager
async def get_httpx_client() -> AsyncIterator[AsyncClient]:
    """Get pre-configured httpx client."""
    timeout = Timeout(30)
    transport = AsyncHTTPTransport(retries=1)
    async with AsyncClient(timeout=timeout, transport=transport) as client:
        yield client
