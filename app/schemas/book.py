from typing import Optional, List, Union, Literal
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.book import BookType

class BookBase(BaseModel):
    title: str
    author: str
    year: int = 0
    country: str = ""
    pages: int = 0

class PhysicalBookCreate(BookBase):
    library_number: Optional[str] = None
    stock_quantity: int = 1

class PhysicalBookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    country: Optional[str] = None
    pages: Optional[int] = None
    library_number: Optional[str] = None
    stock_quantity: Optional[int] = None

class EBookCreate(BookBase):
    file_format: str = "pdf"

class EBookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    country: Optional[str] = None
    pages: Optional[int] = None
    file_format: Optional[str] = None

class BookResponseBase(BookBase):
    id: int
    book_type: BookType
    
    model_config = ConfigDict(from_attributes=True)

class PhysicalBookResponse(BookResponseBase):
    book_type: Literal[BookType.PHYSICAL]
    library_number: Optional[str] = None
    stock_quantity: int
    available_count: int
    is_available: bool

class EBookResponse(BookResponseBase):
    book_type: Literal[BookType.DIGITAL]
    file_url: Optional[str] = None
    file_format: str
    total_installs: int

class EBookInstallResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    installed_at: datetime
    book: Optional[EBookResponse] = None

    model_config = ConfigDict(from_attributes=True)

# For list responses and polymorphic handling
BookResponse = Union[PhysicalBookResponse, EBookResponse]

# Also kept for backward compatibility if needed by other routers
class BookCreate(PhysicalBookCreate):
    pass

class BookUpdate(PhysicalBookUpdate):
    pass
