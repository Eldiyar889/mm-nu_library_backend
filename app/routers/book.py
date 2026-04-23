import os
import shutil
from datetime import datetime, timedelta
from typing import Annotated, List, Union, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, and_, delete, update, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_polymorphic

from app.dependencies import get_db, get_current_librarian, get_current_user
from app.models.book import Book, PhysicalBook, EBook, Borrowing, BorrowingStatus, BookType, EBookInstall
from app.models.user import User, user_favorites, UserRole
from app.schemas.book import (
    BookResponse, PhysicalBookCreate, PhysicalBookUpdate, 
    EBookCreate, EBookUpdate, PhysicalBookResponse, EBookResponse,
    EBookInstallResponse
)
from app.schemas.borrowing import BorrowingResponse, MyBooksResponse

router = APIRouter(prefix="/books", tags=["books"])

@router.get("/", response_model=List[BookResponse])
async def get_all_books(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
):
    """
    Get all books (Physical and Digital) with searching and efficient polymorphic loading.
    """
    # with_polymorphic allows us to join all subclass tables and access their columns in one query
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp)
    
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                wp.title.ilike(search_filter),
                wp.author.ilike(search_filter)
            )
        )
    
    # Efficiently load borrowings for physical books to calculate availability
    query = query.options(selectinload(wp.PhysicalBook.borrowings))
    
    query = query.offset(skip).limit(limit).order_by(desc(wp.id))
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
        book_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get details of a specific book (Physical or Digital)."""
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp).where(wp.id == book_id).options(
        selectinload(wp.PhysicalBook.borrowings)
    )
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/physical", response_model=PhysicalBookResponse, status_code=status.HTTP_201_CREATED)
async def create_physical_book(
    book_in: PhysicalBookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """Create a new physical book."""
    if book_in.library_number:
        query = select(PhysicalBook).where(PhysicalBook.library_number == book_in.library_number)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Physical book with library number '{book_in.library_number}' already exists."
            )

    new_book = PhysicalBook(**book_in.model_dump())
    db.add(new_book)
    await db.commit()
    await db.refresh(new_book)
    
    # Reload with polymorphic mapper and borrowings to satisfy schema
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp).where(wp.id == new_book.id).options(
        selectinload(wp.PhysicalBook.borrowings)
    )
    result = await db.execute(query)
    return result.scalar_one()

@router.patch("/physical/{book_id}", response_model=PhysicalBookResponse)
async def update_physical_book(
    book_id: int,
    book_in: PhysicalBookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """Update a physical book's information."""
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp).where(wp.id == book_id).options(
        selectinload(wp.PhysicalBook.borrowings)
    )
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Physical book not found")
    
    update_data = book_in.model_dump(exclude_unset=True)
    
    if "library_number" in update_data and update_data["library_number"] != book.library_number:
        query = select(PhysicalBook).where(
            and_(
                PhysicalBook.library_number == update_data["library_number"],
                PhysicalBook.id != book_id
            )
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Physical book with library number '{update_data['library_number']}' already exists."
            )

    for field, value in update_data.items():
        setattr(book, field, value)
    
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book

@router.patch("/ebook/{book_id}", response_model=EBookResponse)
async def update_ebook(
    book_id: int,
    book_in: EBookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_librarian: Annotated[User, Depends(get_current_librarian)]
):
    """Update an e-book's information."""
    query = select(EBook).where(EBook.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="E-book not found")
    
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
    """Delete any book (Physical or Digital)."""
    query = select(Book).where(Book.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    await db.delete(book)
    await db.commit()
    return None


# --- Favorites Endpoints ---

@router.post("/{book_id}/favorite", status_code=status.HTTP_200_OK)
async def toggle_favorite(
        book_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Add/Remove book from favorites."""
    # Check if the book exists
    query = select(Book).where(Book.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if already favorited
    query = select(user_favorites).where(
        user_favorites.c.user_id == current_user.id,
        user_favorites.c.book_id == book_id
    )
    result = await db.execute(query)

    if result.first():
        # Remove from favorites
        stmt = delete(user_favorites).where(
            user_favorites.c.user_id == current_user.id,
            user_favorites.c.book_id == book_id
        )
        await db.execute(stmt)
        await db.commit()
        return {"message": "Removed from favorites"}

    # Add to favorites
    stmt = user_favorites.insert().values(user_id=current_user.id, book_id=book_id)
    await db.execute(stmt)
    await db.commit()

    return {"message": "Added to favorites"}

@router.get("/my/favorites", response_model=List[BookResponse])
async def get_my_favorites(
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Get user's favorite books (both physical and digital)."""
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp).join(user_favorites).where(
        user_favorites.c.user_id == current_user.id
    ).options(selectinload(wp.PhysicalBook.borrowings))
    result = await db.execute(query)
    return result.scalars().all()


# --- Borrowing Endpoints (Physical Books only) ---

@router.post("/{book_id}/borrow", response_model=BorrowingResponse)
async def borrow_book(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Reserve a physical book for borrowing."""
    query = select(PhysicalBook).where(PhysicalBook.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    
    if not book:
        raise HTTPException(status_code=404, detail="Physical book not found")

    # Check if stock is available
    active_borrowings_count_query = select(Borrowing).where(
        and_(
            Borrowing.book_id == book_id,
            Borrowing.status.in_([BorrowingStatus.PENDING, BorrowingStatus.ISSUED, BorrowingStatus.OVERDUE])
        )
    )
    result = await db.execute(active_borrowings_count_query)
    active_borrowings_count = len(result.scalars().all())
    
    if active_borrowings_count >= book.stock_quantity:
        raise HTTPException(status_code=400, detail="Book is currently out of stock")

    # Check if user has any overdue books
    query = select(Borrowing).where(
        and_(
            Borrowing.user_id == current_user.id,
            Borrowing.status == BorrowingStatus.OVERDUE
        )
    )
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot borrow a new book until you return your current overdue books."
        )

    new_borrowing = Borrowing(
        user_id=current_user.id,
        book_id=book_id
    )
    db.add(new_borrowing)
    await db.commit()
    await db.refresh(new_borrowing)
    
    query = select(Borrowing).where(Borrowing.id == new_borrowing.id).options(
        selectinload(Borrowing.book).selectinload(PhysicalBook.borrowings),
        selectinload(Borrowing.user)
    )
    result = await db.execute(query)
    return result.scalar_one()


# --- E-Book Specific Endpoints ---

def ebook_form_data(
    title: str = Form(...),
    author: str = Form(...),
    year: int = Form(0),
    country: str = Form("Digital"),
    pages: int = Form(0),
    file_format: str = Form("pdf")
):
    return EBookCreate(
        title=title,
        author=author,
        year=year,
        country=country,
        pages=pages,
        file_format=file_format
    )

@router.post("/upload-ebook", response_model=EBookResponse)
async def upload_ebook(
        db: AsyncSession = Depends(get_db),
        file: UploadFile = File(...),
        data: EBookCreate = Depends(ebook_form_data),
        current_librarian: Annotated[User, Depends(get_current_librarian)] = None
):
    """Upload a new e-book with file."""
    if not os.path.exists("uploads"):
        os.makedirs("uploads")

    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_book = EBook(
        **data.model_dump(),
        file_url=file_path,
        book_type=BookType.DIGITAL
    )

    db.add(new_book)
    await db.commit()
    await db.refresh(new_book)
    return new_book

@router.get("/my/collection", response_model=MyBooksResponse)
async def get_my_collection(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Get both physical borrowings and digital installs in one API."""
    # Fetch Physical Borrowings
    borrowings_query = select(Borrowing).where(
        Borrowing.user_id == current_user.id
    ).options(
        selectinload(Borrowing.book).selectinload(PhysicalBook.borrowings),
        selectinload(Borrowing.user)
    )
    borrowings_result = await db.execute(borrowings_query)
    physical_borrowings = borrowings_result.scalars().all()

    # Fetch Digital Installs
    installs_query = select(EBookInstall).where(
        EBookInstall.user_id == current_user.id
    ).options(selectinload(EBookInstall.book))
    installs_result = await db.execute(installs_query)
    digital_installs = installs_result.scalars().all()

    return {
        "physical_borrowings": physical_borrowings,
        "digital_installs": digital_installs
    }

@router.get("/my/ebooks", response_model=List[EBookInstallResponse])
async def get_my_ebooks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Get list of e-books 'installed' by the current user."""
    query = select(EBookInstall).where(
        EBookInstall.user_id == current_user.id
    ).options(selectinload(EBookInstall.book))
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{book_id}/download")
async def download_ebook(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Download an e-book and increment install count."""
    query = select(EBook).where(EBook.id == book_id)
    result = await db.execute(query)
    ebook = result.scalar_one_or_none()
    
    if not ebook:
        raise HTTPException(status_code=404, detail="E-book not found")
    
    if not ebook.file_url or not os.path.exists(ebook.file_url):
        raise HTTPException(status_code=404, detail="E-book file not found on server")
    
    # Check if already installed by this user to avoid double counting for the same user
    # but we increment total_installs anyway as a global metric
    ebook.total_installs += 1
    
    # Record the installation for the user if not already recorded
    install_query = select(EBookInstall).where(
        and_(EBookInstall.user_id == current_user.id, EBookInstall.book_id == book_id)
    )
    install_result = await db.execute(install_query)
    if not install_result.scalar_one_or_none():
        new_install = EBookInstall(user_id=current_user.id, book_id=book_id)
        db.add(new_install)
    
    await db.commit()
    
    return FileResponse(
        path=ebook.file_url,
        filename=f"{ebook.title}.{ebook.file_format}",
        media_type='application/octet-stream'
    )


# --- Generic Librarian Management ---

@router.post("/borrowings/{borrowing_id}/issue", response_model=BorrowingResponse)
async def issue_book(
        borrowing_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_librarian: Annotated[User, Depends(get_current_librarian)],
        days: int = 14
):
    """Librarian: Issue a reserved physical book."""
    query = select(Borrowing).where(Borrowing.id == borrowing_id).options(
        selectinload(Borrowing.book).selectinload(PhysicalBook.borrowings),
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
    borrowing.due_date = datetime.now() + timedelta(days=days)
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
    """Librarian: Mark a book as returned."""
    query = select(Borrowing).where(Borrowing.id == borrowing_id).options(
        selectinload(Borrowing.book).selectinload(PhysicalBook.borrowings),
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

@router.get("/new", response_model=List[BookResponse])
async def get_new_books(
        db: Annotated[AsyncSession, Depends(get_db)],
        limit: int = 10,
):
    """Get most recently added books."""
    wp = with_polymorphic(Book, [PhysicalBook, EBook])
    query = select(wp).order_by(desc(wp.id)).limit(limit).options(
        selectinload(wp.PhysicalBook.borrowings)
    )
    result = await db.execute(query)
    return result.scalars().all()
