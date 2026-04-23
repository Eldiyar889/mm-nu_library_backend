import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, func, Enum, String, CheckConstraint, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database import Base


# --- Enums ---

class BookType(enum.Enum):
    PHYSICAL = "physical"
    DIGITAL = "digital"

class BorrowingStatus(enum.Enum):
    PENDING = "pending"  # Student reserved it
    ISSUED = "issued"  # Librarian handed it over
    RETURNED = "returned"  # Book is back on shelf
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


# --- Association Tables ---

# If we want separate favorites, we'd define them here, 
# but currently we have user_favorites in user.py that points to Book.id.
# I'll stick to that for now, but we can have specific ones if needed.


# --- Models ---

class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(255), index=True)
    year: Mapped[int] = mapped_column(default=0)
    country: Mapped[str] = mapped_column(String(255), default="")
    pages: Mapped[int] = mapped_column(default=0)
    
    book_type: Mapped[BookType] = mapped_column(Enum(BookType), nullable=False)

    # Relationships
    favorited_by: Mapped[List["User"]] = relationship(
        "User", secondary="user_favorites", back_populates="favorites"
    )

    __mapper_args__ = {
        "polymorphic_on": book_type,
        "polymorphic_identity": "book",
    }


class PhysicalBook(Book):
    """
    Limited college resource. Requires stock management
    and librarian interaction.
    """
    __tablename__ = "physical_books"

    id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    library_number: Mapped[str] = mapped_column(String(100), index=True, nullable=True)

    # Inventory Management
    stock_quantity: Mapped[int] = mapped_column(default=1)

    # Relationships
    borrowings: Mapped[List["Borrowing"]] = relationship("Borrowing", back_populates="book")

    __mapper_args__ = {
        "polymorphic_identity": BookType.PHYSICAL,
    }

    @property
    def available_count(self) -> int:
        active_statuses = [BorrowingStatus.PENDING, BorrowingStatus.ISSUED, BorrowingStatus.OVERDUE]
        active_borrowings = sum(1 for b in self.borrowings if b.status in active_statuses)
        return max(0, self.stock_quantity - active_borrowings)

    @property
    def is_available(self) -> bool:
        return self.available_count > 0


class EBook(Book):
    """
    Infinite digital resource. Students can "install" or download
    this immediately without a librarian.
    """
    __tablename__ = "ebooks"

    id: Mapped[int] = mapped_column(ForeignKey("books.id"), primary_key=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=True)
    file_format: Mapped[str] = mapped_column(String(10), default="pdf")  # pdf, epub, etc.

    # Metrics (Instead of Borrowing status)
    total_installs: Mapped[int] = mapped_column(default=0)
    
    # Relationships
    installs: Mapped[List["EBookInstall"]] = relationship("EBookInstall", back_populates="book")

    __mapper_args__ = {
        "polymorphic_identity": BookType.DIGITAL,
    }


class EBookInstall(Base):
    """
    Tracks which user has "installed" (downloaded) a digital book.
    Since digital books don't need returning, this is a permanent record.
    """
    __tablename__ = "ebook_installs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("ebooks.id"), index=True)
    installed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User")
    book: Mapped["EBook"] = relationship(back_populates="installs")


class Borrowing(Base):
    """
    Tracks the lifecycle of a PHYSICAL book only.
    """
    __tablename__ = "borrowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("physical_books.id"), index=True)
    librarian_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    status: Mapped[BorrowingStatus] = mapped_column(
        Enum(BorrowingStatus), default=BorrowingStatus.PENDING
    )

    # Timestamps
    reserved_at: Mapped[datetime] = mapped_column(server_default=func.now())
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    librarian: Mapped["User | None"] = relationship("User", foreign_keys=[librarian_id])
    book: Mapped["PhysicalBook"] = relationship(back_populates="borrowings")

    @hybrid_property
    def is_late(self) -> bool:
        if self.status == BorrowingStatus.ISSUED and self.due_date:
            return datetime.now() > self.due_date
        return False