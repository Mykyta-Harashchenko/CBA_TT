from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import csv
import io
import json

from fastapi import Depends, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from passlib.context import CryptContext
from jose import jwt, JWTError

from schemas import (
    UserSignup, UserSignin, BookCreate, BookUpdate, BookOut, BulkImportResult,
    DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, CURRENT_YEAR, book_genres
)
from db import get_db
from conf.config import config


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = config.SECRET_KEY_JWT
ALGORITHM = config.ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/test_task/signin")


# ---------- Auth Helpers ----------

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[float] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        timedelta(seconds=expires_delta) if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "access_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def create_refresh_token(data: dict, expires_delta: Optional[float] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        timedelta(seconds=expires_delta) if expires_delta else timedelta(days=7)
    )
    to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def authenticate_user(db: AsyncSession, email: str, password: str):
    query = text("SELECT * FROM users WHERE email = :email")
    result = await db.execute(query, {"email": email})
    user = result.mappings().first()

    if user is None or not pwd_context.verify(password, user["hashed_password"]):
        return False
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        query = text("SELECT * FROM users WHERE email = :email LIMIT 1")
        result = await db.execute(query, {"email": email})
        user_row = result.mappings().first()

        if user_row is None:
            raise credentials_exception

        return user_row
    except JWTError:
        raise credentials_exception


# ---------- User Services ----------

async def signup(user: UserSignup, db: AsyncSession) -> Dict[str, Any]:
    query_check = text("SELECT id FROM users WHERE email = :email")
    result = await db.execute(query_check, {"email": user.email})
    if result.scalar():
        raise HTTPException(status_code=400, detail="Email already registered")

    query_count = text("SELECT COUNT(*) FROM users")
    result = await db.execute(query_count)
    count = result.scalar() or 0

    hashed_password = get_password_hash(user.password)

    query_insert = text("""
        INSERT INTO users (email, username, hashed_password)
        VALUES (:email, :username, :hashed_password)
        RETURNING id
    """)
    result = await db.execute(query_insert, {
        "email": user.email,
        "username": user.username,
        "hashed_password": hashed_password
    })
    new_user_id = result.scalar()
    await db.commit()

    return {"msg": "User created successfully", 
        "user_id": new_user_id,
        "email": user.email,         
        "username": user.username, }


async def signin(user: UserSignin, db: AsyncSession) -> Dict[str, Any]:
    db_user = await authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": db_user["email"]})
    refresh_token = await create_refresh_token(data={"sub": db_user["email"]})

    query_update = text("UPDATE users SET refresh_token = :rt WHERE id = :id")
    await db.execute(query_update, {"rt": refresh_token, "id": db_user["id"]})
    await db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


async def signout(user_email: str, db: AsyncSession):
    query_update = text("UPDATE users SET refresh_token = NULL WHERE email = :email")
    await db.execute(query_update, {"email": user_email})
    await db.commit()
    return {"msg": "Successfully logged out"}


async def refresh_token(refresh_token: str, db: AsyncSession):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    query = text("SELECT id, email, refresh_token FROM users WHERE email = :email")
    result = await db.execute(query, {"email": email})
    user = result.mappings().first()

    if user is None or user["refresh_token"] != refresh_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    access_token = create_access_token(data={"sub": email})
    return {"access_token": access_token, "token_type": "bearer"}

# ---------- Helpers ----------

async def _get_or_create_author(session: AsyncSession, full_name: str) -> int:
    """Создать автора, если его нет. Вернуть ID"""
    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Author name cannot be empty")

    q_find = text("SELECT id FROM authors WHERE full_name = :full_name")
    res = await session.execute(q_find, {"full_name": full_name})
    row = res.scalar()
    if row:
        return int(row)

    # Для SQLite нельзя использовать RETURNING, поэтому делаем вставку и потом получаем id
    await session.execute(text("INSERT INTO authors (full_name) VALUES (:full_name)"), {"full_name": full_name})
    await session.commit()
    q_last = text("SELECT id FROM authors WHERE full_name = :full_name ORDER BY id DESC LIMIT 1")
    res = await session.execute(q_last, {"full_name": full_name})
    author_id = res.scalar()
    if not author_id:
        raise HTTPException(status_code=500, detail="Failed to create author")
    return int(author_id)


# ---------- Book Services ----------

async def create_book(book: BookCreate, db: AsyncSession, current_user: dict) -> BookOut:
    author_id = await _get_or_create_author(db, book.author)

    q_insert = text("""
        INSERT INTO books (title, author_id, published_year, genre, created_at)
        VALUES (:title, :author_id, :published_year, :genre, CURRENT_TIMESTAMP)
    """)
    params = {
        "title": book.title.strip(),
        "author_id": author_id,
        "published_year": book.published_year,
        "genre": book.genre.strip() if book.genre else None,
    }
    await db.execute(q_insert, params)
    await db.commit()

    q_select = text("""
        SELECT b.id, b.title, a.full_name AS author, b.published_year, b.genre, b.created_at
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE b.id = (SELECT MAX(id) FROM books)
    """)
    result = await db.execute(q_select)
    created = result.mappings().first()
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create book")
    return BookOut(**created)


async def update_book(book_id: int, payload: BookUpdate, db: AsyncSession, current_user: dict) -> BookOut:
    q_load = text("SELECT id FROM books WHERE id = :id")
    res = await db.execute(q_load, {"id": book_id})
    if not res.scalar():
        raise HTTPException(status_code=404, detail="Book not found")

    update_fields = {}
    if payload.title: update_fields["title"] = payload.title.strip()
    if payload.published_year: update_fields["published_year"] = payload.published_year
    if payload.genre: update_fields["genre"] = payload.genre.strip()

    if payload.author:
        author_id = await _get_or_create_author(db, payload.author.strip())
        update_fields["author_id"] = author_id

    if update_fields:
        set_sql = ", ".join([f"{k} = :{k}" for k in update_fields.keys()])
        update_fields["id"] = book_id
        q_upd = text(f"UPDATE books SET {set_sql} WHERE id = :id")
        await db.execute(q_upd, update_fields)
        await db.commit()

    return await get_book(book_id, db)


async def delete_book(book_id: int, db: AsyncSession, current_user: dict) -> bool:
    q = text("SELECT id FROM books WHERE id = :id")
    res = await db.execute(q, {"id": book_id})
    if not res.scalar():
        return False

    await db.execute(text("DELETE FROM books WHERE id = :id"), {"id": book_id})
    await db.commit()
    return True


async def bulk_import(file: UploadFile, db: AsyncSession, current_user: dict) -> BulkImportResult:
    """Импорт книг из CSV или JSON"""
    content = await file.read()
    text_content = content.decode("utf-8")
    rows_to_insert = []
    errors = []

    if file.filename.lower().endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(text_content))
            for idx, row in enumerate(reader, start=1):
                rows_to_insert.append((idx, row))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")
    elif file.filename.lower().endswith(".json"):
        try:
            data = json.loads(text_content)
            if not isinstance(data, list):
                raise HTTPException(status_code=400, detail="JSON must be an array of book objects")
            for idx, item in enumerate(data, start=1):
                rows_to_insert.append((idx, item))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use .csv or .json")

    inserted = 0
    for idx, raw in rows_to_insert:
        try:
            title = (raw.get("title") or "").strip()
            author = (raw.get("author") or "").strip()
            published_year = raw.get("published_year")
            genre = raw.get("genre")

            if isinstance(published_year, str) and published_year.isdigit():
                published_year = int(published_year)

            if not title:
                raise ValueError("title is required")
            if not author:
                raise ValueError("author is required")
            if not isinstance(published_year, int):
                raise ValueError("published_year must be integer")
            if published_year < 1800 or published_year > CURRENT_YEAR:
                raise ValueError(f"published_year must be between 1800 and {CURRENT_YEAR}")
            if genre not in book_genres:
                raise ValueError(f"genre must be one of: {', '.join(sorted(book_genres))}")

            author_id = await _get_or_create_author(db, author)
            q_insert = text("""
                INSERT INTO books (title, author_id, published_year, genre, created_at)
                VALUES (:title, :author_id, :published_year, :genre, CURRENT_TIMESTAMP)
            """)
            await db.execute(q_insert, {
                "title": title,
                "author_id": author_id,
                "published_year": published_year,
                "genre": genre,
            })
            inserted += 1
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})

    await db.commit()
    return BulkImportResult(inserted=inserted, errors=errors)


async def list_books(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    title: Optional[str] = None,
    author: Optional[str] = None,
    genre: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sort_by: str = "title",
    sort_order: str = "asc",
) -> List[BookOut]:

    try:
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="page and page_size must be integers")
    
    allowed_sort_columns = {"title": "b.title", "published_year": "b.published_year", "author": "a.full_name"}
    sort_col = allowed_sort_columns.get(sort_by)
    if not sort_col:
        raise HTTPException(status_code=400, detail=f"sort_by must be one of {list(allowed_sort_columns.keys())}")

    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="sort_order must be 'asc' or 'desc'")

    where_clauses = []
    params: Dict[str, Any] = {}

    if title:
        where_clauses.append("b.title ILIKE :title")
        params["title"] = f"%{title}%"
    if author:
        where_clauses.append("a.full_name ILIKE :author")
        params["author"] = f"%{author}%"
    if genre:
        where_clauses.append("b.genre ILIKE :genre")
        params["genre"] = f"%{genre}%"
    if year_from:
        where_clauses.append("b.published_year >= :year_from")
        params["year_from"] = year_from
    if year_to:
        where_clauses.append("b.published_year <= :year_to")
        params["year_to"] = year_to

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    order_sql = f"ORDER BY {sort_col} {sort_order.upper()}"
    offset = (page - 1) * page_size
    params.update({"limit": page_size, "offset": offset})

    q = text(f"""
        SELECT b.id, b.title, a.full_name AS author, b.published_year, b.genre, b.created_at
        FROM books b
        JOIN authors a ON a.id = b.author_id
        {where_sql}
        {order_sql}
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(q, params)
    rows = result.mappings().all()
    return [BookOut(**r) for r in rows]


async def get_book(book_id: int, db: AsyncSession) -> BookOut:
    q = text("""
        SELECT b.id, b.title, a.full_name AS author, b.published_year, b.genre, b.created_at
        FROM books b
        JOIN authors a ON a.id = b.author_id
        WHERE b.id = :id
    """)
    result = await db.execute(q, {"id": book_id})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookOut(**row)
