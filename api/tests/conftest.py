from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_draw_api.executor import FakeExecutor
from ai_draw_api.main import create_app
from ai_draw_api.store import JobStore


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "jobs.db"


@pytest_asyncio.fixture
async def store(db_path):
    store = JobStore(db_path)
    await store.open()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def client(db_path):
    app = create_app(
        store=JobStore(db_path), executor=FakeExecutor(duel_seconds=0.0)
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
