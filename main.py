from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, APIRouter, status, Query, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
import csv, json, io

from db import get_db
from services import (
    signup,
    signin,
    signout,
    create_book,
    list_books,
    get_book,
    update_book,
    delete_book,
    bulk_import,
    get_current_user,
)
from schemas import UserSignup, UserSignin, BookCreate, BookUpdate, BookOut, BulkImportResult

# --- FastAPI app ---
@asynccontextmanager
async def lifespan(_: FastAPI):
    yield

app = FastAPI(
    lifespan=lifespan,
    title="Library API",
    description="""
A simple API for managing books and users.

**Authentication:**  
- Use `/test_task/signup` to register.
- Use `/test_task/signin` to get a JWT token.  
  **Note:** In the login form, enter your **email** in the `username` field (OAuth2 standard limitation).
- Use the token for all protected endpoints (books, import, etc).

**Books:**  
- CRUD operations for books.
- Bulk import from CSV or JSON.
- Filtering, sorting, and pagination.

**Bulk Import:**  
- Accepts `.csv` or `.json` files.
- JSON must be an array of book objects.
- CSV must have columns: `title,author,published_year,genre`.

**Authorization:**  
- All book endpoints require authentication (Bearer token).

**See the "Schemas" section below for request/response models and examples.**
""",
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/test_task")

# --- User endpoints ---
@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with email, username, and password."
)
async def register(user: UserSignup, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.  
    Returns user info and user ID.
    """
    try:
        return await signup(user, db)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering user: {str(e)}")


@router.post(
    "/signin",
    status_code=status.HTTP_200_OK,
    summary="Sign in (get JWT token)",
    description="""
Authenticate and get a JWT token.

**IMPORTANT:**  
In the login form, enter your **email** in the `username` field (OAuth2PasswordRequestForm limitation).
"""
)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT tokens.
    """
    try:
        user_signin = UserSignin(email=form_data.username, password=form_data.password)
        return await signin(user_signin, db)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error signing in: {str(e)}")


@router.post(
    "/signout",
    status_code=status.HTTP_200_OK,
    summary="Sign out",
    description="Sign out the current user (token blacklist if implemented)."
)
async def logout(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Sign out the current user.
    """
    try:
        return await signout(current_user, db)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error signing out: {str(e)}")


# --- Book endpoints ---
@router.post(
    "/",
    response_model=BookOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new book",
    description="Add a new book to the library. Requires authentication."
)
async def add_book(book: BookCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """
    Add a new book.  
    Requires authentication.
    """
    try:
        return await create_book(book, db, user)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding book: {str(e)}")


@router.get(
    "/",
    response_model=List[BookOut],
    status_code=status.HTTP_200_OK,
    summary="List books",
    description="""
Get a paginated list of books.  
Supports filtering by title, author, genre, year range, and sorting.
"""
)
async def get_books(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Books per page"),
    title: Optional[str] = Query(None, description="Filter by title"),
    author: Optional[str] = Query(None, description="Filter by author"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    year_from: Optional[int] = Query(None, description="Published year from"),
    year_to: Optional[int] = Query(None, description="Published year to"),
    sort_by: str = Query("title", description="Sort by field"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """
    List books with filters, pagination, and sorting.
    """
    try:
        return await list_books(db, page, page_size, title, author, genre, year_from, year_to, sort_by, sort_order)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching books: {str(e)}")


@router.get(
    "/{book_id}",
    response_model=BookOut,
    status_code=status.HTTP_200_OK,
    summary="Get book by ID",
    description="Get a single book by its ID."
)
async def get_book_by_id(book_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a book by its ID.
    """
    try:
        book = await get_book(book_id, db)
        if not book:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        return book
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching book: {str(e)}")


@router.put(
    "/{book_id}",
    response_model=BookOut,
    status_code=status.HTTP_200_OK,
    summary="Update book by ID",
    description="Update an existing book by its ID. Requires authentication."
)
async def update_book_by_id(book_id: int, book: BookUpdate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """
    Update a book by its ID.  
    Requires authentication.
    """
    try:
        updated = await update_book(book_id, book, db, user)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        return updated
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating book: {str(e)}")


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete book by ID",
    description="Delete a book by its ID. Requires authentication."
)
async def delete_book_by_id(book_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """
    Delete a book by its ID.  
    Requires authentication.
    """
    try:
        deleted = await delete_book(book_id, db, user)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        return
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting book: {str(e)}")


# --- Bulk import endpoint ---
@router.post(
    "/bulk-import",
    response_model=BulkImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import books",
    description="""
Bulk import books from a CSV or JSON file.

- **CSV:** Must have columns: `title,author,published_year,genre`
- **JSON:** Must be an array of book objects.

Returns the number of books inserted and a list of errors (if any).
Requires authentication.
"""
)
async def bulk_import_books(file: UploadFile, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """
    Bulk import books from a file.
    """
    if not file.filename.lower().endswith((".csv", ".json")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only CSV or JSON is allowed."
        )
    try:
        return await bulk_import(file, db, user)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during bulk import: {str(e)}"
        )


# --- Healthcheck ---
@app.get(
    "/api/healthchecker",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the API and database are working."
)
async def healthchecker(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        if not result.fetchone():
            raise HTTPException(status_code=500, detail="Database is not configured correctly")
        return {"message": "Welcome to FastAPI!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")


# --- Register router ---
app.include_router(router)