from datetime import datetime, timedelta
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_librarian, get_current_user
from app.models.book import Books, Borrowing, BorrowingStatus
from app.models.user import User, user_favorites
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


# --- Favorites Endpoints ---

@router.post("/{book_id}/favorite", status_code=status.HTTP_200_OK)
async def add_book_to_favorites(
        book_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    # Check if book exists
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if already in favorites
    query = select(user_favorites).where(
        and_(user_favorites.c.user_id == current_user.id, user_favorites.c.book_id == book_id)
    )
    result = await db.execute(query)
    if result.one_or_none():
        return {"message": "Book already in favorites"}

    # Add to favorites
    stmt = user_favorites.insert().values(user_id=current_user.id, book_id=book_id)
    await db.execute(stmt)
    await db.commit()
    return {"message": "Book added to favorites"}


@router.delete("/{book_id}/favorite", status_code=status.HTTP_200_OK)
async def remove_book_from_favorites(
        book_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    # Check if book exists
    query = select(Books).where(Books.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Remove from favorites
    stmt = delete(user_favorites).where(
        and_(user_favorites.c.user_id == current_user.id, user_favorites.c.book_id == book_id)
    )
    await db.execute(stmt)
    await db.commit()
    return {"message": "Book removed from favorites"}


@router.get("/my/favorites", response_model=List[BookResponse])
async def get_my_favorites(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    query = select(Books).join(user_favorites).where(user_favorites.c.user_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()

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

    # Check if user has any unreturned books (ISSUED or OVERDUE)
    query = select(Borrowing).where(
        and_(
            Borrowing.user_id == current_user.id,
            Borrowing.status.in_([BorrowingStatus.ISSUED, BorrowingStatus.OVERDUE])
        )
    )
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot borrow a new book until you return your current one."
        )

    new_borrowing = Borrowing(
        user_id=current_user.id,
        book_id=book_id
    )
    db.add(new_borrowing)
    await db.commit()
    await db.refresh(new_borrowing)
    
    query = select(Borrowing).where(Borrowing.id == new_borrowing.id).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user),
        selectinload(Borrowing.librarian)
    )
    result = await db.execute(query)
    return result.scalar_one()


@router.post("/borrowings/{borrowing_id}/cancel", response_model=BorrowingResponse)
async def cancel_borrowing(
        borrowing_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Cancel a PENDING or OVERDUE (not yet issued) borrowing.
    Users can cancel their own; librarians can cancel any.
    """
    query = select(Borrowing).where(Borrowing.id == borrowing_id).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user),
        selectinload(Borrowing.librarian)
    )
    result = await db.execute(query)
    borrowing = result.scalar_one_or_none()

    if not borrowing:
        raise HTTPException(status_code=404, detail="Borrowing record not found")

    # Check permission: owner or librarian
    if borrowing.user_id != current_user.id and not current_user.is_librarian:
        raise HTTPException(status_code=403, detail="Not enough permissions to cancel this borrowing")

    # Only allow cancellation if not yet issued
    if borrowing.status not in [BorrowingStatus.PENDING, BorrowingStatus.OVERDUE]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel borrowing with status {borrowing.status}")

    if borrowing.issued_at is not None:
        raise HTTPException(status_code=400, detail="Cannot cancel a book that has already been issued")

    borrowing.status = BorrowingStatus.CANCELLED
    await db.commit()
    await db.refresh(borrowing)
    return borrowing


async def update_overdue_borrowings(db: AsyncSession):
    """
    Update PENDING borrowings to OVERDUE if they are older than 1 day.
    Update ISSUED borrowings to OVERDUE if they passed due_date.
    """
    now = datetime.now()
    reservation_threshold = now - timedelta(days=1)

    # 1. Check reservation expiration
    stmt1 = (
        update(Borrowing)
        .where(
            and_(
                Borrowing.status == BorrowingStatus.PENDING,
                Borrowing.reserved_at < reservation_threshold
            )
        )
        .values(status=BorrowingStatus.OVERDUE)
    )

    # 2. Check return deadline
    stmt2 = (
        update(Borrowing)
        .where(
            and_(
                Borrowing.status == BorrowingStatus.ISSUED,
                Borrowing.due_date < now
            )
        )
        .values(status=BorrowingStatus.OVERDUE)
    )

    await db.execute(stmt1)
    await db.execute(stmt2)
    await db.commit()


@router.get("/my/books", response_model=List[BorrowingResponse])
async def get_my_borrowings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    await update_overdue_borrowings(db)
    query = select(Borrowing).where((Borrowing.user_id == current_user.id)).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user),
        selectinload(Borrowing.librarian)
    )
    result = await db.execute(query)
    return result.scalars().all()


# --- Librarian Borrowing Management ---

@router.get("/borrowings/all", response_model=List[BorrowingResponse])
async def get_all_borrowings(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """
    Get all borrowings in the system. Accessible only by librarians.
    """
    await update_overdue_borrowings(db)
    query = select(Borrowing).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user),
        selectinload(Borrowing.librarian)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/borrowings/{borrowing_id}/issue", response_model=BorrowingResponse)
async def issue_book(
        borrowing_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """
    Mark a borrowing as ISSUED. Set issued_at, due_date (14 days), and librarian_id.
    """
    query = select(Borrowing).where(Borrowing.id == borrowing_id).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user)
    )
    result = await db.execute(query)
    borrowing = result.scalar_one_or_none()

    if not borrowing:
        raise HTTPException(status_code=404, detail="Borrowing record not found")

    if borrowing.status not in [BorrowingStatus.PENDING, BorrowingStatus.OVERDUE]:
        raise HTTPException(status_code=400, detail=f"Cannot issue book with status {borrowing.status}")

    borrowing.status = BorrowingStatus.ISSUED
    borrowing.issued_at = datetime.now()
    borrowing.due_date = datetime.now() + timedelta(days=14)
    borrowing.librarian_id = current_librarian.id

    await db.commit()
    await db.refresh(borrowing)
    return borrowing


@router.post("/borrowings/{borrowing_id}/return", response_model=BorrowingResponse)
async def return_book(
        borrowing_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """
    Mark a borrowing as RETURNED. Set returned_at and update librarian_id.
    """
    query = select(Borrowing).where(Borrowing.id == borrowing_id).options(
        selectinload(Borrowing.book),
        selectinload(Borrowing.user)
    )
    result = await db.execute(query)
    borrowing = result.scalar_one_or_none()

    if not borrowing:
        raise HTTPException(status_code=404, detail="Borrowing record not found")

    if borrowing.status not in [BorrowingStatus.ISSUED, BorrowingStatus.OVERDUE]:
        raise HTTPException(status_code=400, detail="Only issued or overdue books can be returned")

    borrowing.status = BorrowingStatus.RETURNED
    borrowing.returned_at = datetime.now()
    borrowing.librarian_id = current_librarian.id

    await db.commit()
    await db.refresh(borrowing)
    return borrowing
