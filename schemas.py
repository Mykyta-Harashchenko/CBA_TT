from pydantic import BaseModel, validator, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

book_genres=['Fiction', 'Non-fiction', 'Science', 'History']
book_genres_lower = [g.lower() for g in book_genres]
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
CURRENT_YEAR = 2025

class BookCreate(BaseModel):
    title: str
    published_year: int
    author: str
    genre: str
    
    @validator('genre')
    def genre_valid(cls, genre):
        if genre.lower() not in book_genres_lower:
            raise ValueError(f"Enter appropriate genre: {', '.join(book_genres)}")
        idx = book_genres_lower.index(genre.lower())
        return book_genres[idx]
    
    @validator('published_year')
    def published_year_valid(cls, published_year):
        if published_year < 1800 or published_year > CURRENT_YEAR:
            raise ValueError('Enter a valid published year(between 1800 and Current year)')
        return published_year

class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    author: Optional[str] = Field(None, min_length=1)
    published_year: Optional[int] = None
    genre: Optional[str] = None
    
    @validator('published_year')
    def published_year_valid(cls, published_year):
        if published_year < 1800 or published_year > CURRENT_YEAR:
            raise ValueError('Enter a valid published year(between 1800 and Current year)')
        return published_year

    @validator('genre')
    def genre_valid(cls, genre):
        if genre.lower() not in book_genres_lower:
            raise ValueError(f"Enter appropriate genre: {', '.join(book_genres)}")
        idx = book_genres_lower.index(genre.lower())
        return book_genres[idx]


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    published_year: int
    genre: str
    created_at: datetime


class BulkImportResult(BaseModel):
    inserted: int
    errors: List[Dict[str, Any]]


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class UserSignin(BaseModel):
    email: str
    password: str


class UserSignup(BaseModel):
    email: EmailStr
    username: str
    password: str

class Author(BaseModel):
    fullname: str