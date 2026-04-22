from datetime import datetime
import enum
from typing import List

from sqlalchemy import String, Boolean, DateTime, func, Table, Column, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
)

class UserRole(enum.Enum):
    LIBRARIAN = "LIBRARIAN"
    STUDENT = "STUDENT"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    group: Mapped[str] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    role: Mapped[Enum(UserRole)] = mapped_column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    borrowed_books: Mapped[list["Borrowing"]] = relationship(
        "Borrowing",
        foreign_keys="Borrowing.user_id",
        back_populates="user"
    )

    favorites: Mapped[List["Book"]] = relationship(
        "Book",
        secondary=user_favorites,
        back_populates="favorited_by"
    )

    installed_ebooks: Mapped[List["EBookInstall"]] = relationship(
        "EBookInstall",
        back_populates="user"
    )
