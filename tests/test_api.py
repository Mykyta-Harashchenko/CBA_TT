import sys
import pathlib
import uuid

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

import pytest

@pytest.mark.asyncio
async def test_healthchecker(client):
    response = await client.get("/api/healthchecker")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to FastAPI!"

async def signup_user(client, email=None, username=None, password="secret"):
    if email is None:
        email = f"user_{uuid.uuid4().hex}@example.com"
    if username is None:
        username = f"user_{uuid.uuid4().hex[:8]}"
    signup_data = {"email": email, "username": username, "password": password}
    response = await client.post("/test_task/signup", json=signup_data)
    assert response.status_code in (201, 409)
    return email, username, password

async def get_valid_token(client, email, password):
    form_data = {"username": email, "password": password}
    response = await client.post("/test_task/signin", data=form_data)
    assert response.status_code == 200
    assert "access_token" in response.json()
    return response.json()["access_token"]

@pytest.mark.asyncio
async def test_signup_and_signin(client):
    email, username, password = await signup_user(client)
    token = await get_valid_token(client, email=email, password=password)
    assert token

@pytest.mark.asyncio
async def test_create_get_delete_book(client):
    email, username, password = await signup_user(client)
    access_token = await get_valid_token(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {access_token}"}

    book_data = {"title": "Book1", "author": "Author1", "published_year": 2020, "genre": "Fiction"}
    response = await client.post("/test_task/", json=book_data, headers=headers)
    assert response.status_code == 201
    book_id = response.json()["id"]

    response = await client.get(f"/test_task/{book_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Book1"

    response = await client.delete(f"/test_task/{book_id}", headers=headers)
    assert response.status_code == 204

@pytest.mark.asyncio
async def test_bulk_import_endpoint(client):
    email, username, password = await signup_user(client)
    access_token = await get_valid_token(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {access_token}"}
    csv_content = "title,author,published_year,genre\nBook1,Author1,2020,Fiction"
    files = {"file": ("books.csv", csv_content, "text/csv")}
    response = await client.post("/test_task/bulk-import", files=files, headers=headers)
    assert response.status_code == 201
    json_resp = response.json()
    assert "inserted" in json_resp
    assert "errors" in json_resp