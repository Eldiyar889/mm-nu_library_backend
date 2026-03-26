from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_librarian, get_current_user
from app.models.book import Books, Borrowing
from app.models.user import User
from app.schemas.book import BookCreate, BookUpdate, BookResponse
from app.schemas.borrowing import BorrowingResponse

router = APIRouter(prefix="/books", tags=["books"])

@router.get("/", response_model=List[BookResponse])
async def get_all_books(
    db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100
):
    query = select(Books).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
        book_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_in: BookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    new_book = Books(**book_in.model_dump())
    db.add(new_book)
    await db.commit()
    await db.refresh(new_book)
    return new_book

@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int,
    book_in: BookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    update_data = book_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)
    
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book

@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    await db.delete(book)
    await db.commit()
    return None

# --- Borrowing Endpoints (User) ---

@router.post("/{book_id}/borrow", response_model=BorrowingResponse)
async def borrow_book(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    query = select(Borrowing).where(
        and_(Borrowing.book_id == book_id, Borrowing.returned_at == None)
    )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Book is already borrowed")

    new_borrowing = Borrowing(
        user_id=current_user.id,
        book_id=book_id
    )
    db.add(new_borrowing)
    await db.commit()
    await db.refresh(new_borrowing)
    
    query = select(Borrowing).where(Borrowing.id == new_borrowing.id).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user)
    )
    result = await db.execute(query)
    return result.scalar_one()

@router.get("/my/borrowings", response_model=List[BorrowingResponse])
async def get_my_borrowings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    query = select(Borrowing).where((Borrowing.user_id == current_user.id)).options(selectinload(Borrowing.book))
    result = await db.execute(query)
    return result.scalars().all()
