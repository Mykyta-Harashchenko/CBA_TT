import sys
import pathlib
import os

import pytest_asyncio
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from main import app
from db import get_db


sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_db.sqlite" 

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} 
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db():
    db_path = "./test_db.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
    async with engine.begin() as conn:
        with open("db_mig_tests.sql", "r") as f:
            sql = f.read()
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(text(stmt))

@pytest_asyncio.fixture(scope="module")
async def db_session():
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="module")
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(base_url="http://test", transport=transport) as ac:
            yield ac
    app.dependency_overrides.clear()
