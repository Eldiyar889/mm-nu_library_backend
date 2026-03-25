from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.schemas.book import BookResponse
from app.schemas.user import UserRead

class BorrowingBase(BaseModel):
    book_id: int
    user_id: int

class BorrowingCreate(BaseModel):
    book_id: int

class BorrowingReturn(BaseModel):
    borrowing_id: int

class BorrowingResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    borrowed_at: datetime
    due_date: datetime
    returned_at: Optional[datetime] = None
    book: BookResponse
    user: Optional[UserRead] = None
    librarian: Optional[UserRead] = None # Added to show who processed the return

    class Config:
        from_attributes = True
