from typing import Optional
from pydantic import BaseModel

class BookBase(BaseModel):
    title: str
    author: str
    year: int
    country: str
    pages: int
    library_number: str

class BookCreate(BookBase):
    pass

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    country: Optional[str] = None
    pages: Optional[int] = None
    library_number: Optional[str] = None

class BookResponse(BookBase):
    id: int

    class Config:
        from_attributes = True
