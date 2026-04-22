from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.book import BorrowingStatus
from app.schemas.book import BookResponse, EBookInstallResponse
from app.schemas.user import UserRead
from typing import List

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
    status: BorrowingStatus
    reserved_at: datetime
    issued_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    book: BookResponse
    user: Optional[UserRead] = None
    librarian: Optional[UserRead] = None

    class Config:
        from_attributes = True

class MyBooksResponse(BaseModel):
    physical_borrowings: List[BorrowingResponse]
    digital_installs: List[EBookInstallResponse]

    class Config:
        from_attributes = True
