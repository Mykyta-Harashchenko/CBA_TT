import sys
import pathlib
import io
import json
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from fastapi import UploadFile
from schemas import UserSignup, UserSignin, BookCreate
from services import signup, signin, create_book, bulk_import

@pytest.mark.asyncio
async def test_signup(db_session):
    user = UserSignup(email="test@example.com", username="testuser", password="password123")
    result = await signup(user, db_session)
    assert result["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_signin(db_session):
    user_signin = UserSignin(email="test@example.com", password="password123")
    result = await signin(user_signin, db_session)
    assert "access_token" in result

@pytest.mark.asyncio
async def test_create_book(db_session):
    book = BookCreate(title="Test Book", author="Author", published_year=2020, genre="Fiction")
    user = {"id": 1} 
    result = await create_book(book, db_session, user)
    assert result.title == "Test Book"

@pytest.mark.asyncio
async def test_bulk_import(db_session):
    books = [
        {"title": "The Hobbit", "author": "J.R.R. Tolkien", "published_year": 1937, "genre": "History"},
        {"title": "Dune", "author": "Frank Herbert", "published_year": 1965, "genre": "Fiction"},
        {"title": "Invalid Book", "author": "Unknown", "published_year": "Year2020", "genre": "Fiction"}
    ]
    json_content = json.dumps(books)
    upload_file = UploadFile(filename="books.json", file=io.BytesIO(json_content.encode()))
    user = {"id": 1}
    result = await bulk_import(upload_file, db_session, user)
    assert result.inserted == 2
    assert len(result.errors) == 1
