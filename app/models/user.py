from datetime import datetime
from typing import List

from sqlalchemy import String, Boolean, DateTime, func, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Association table for favorites (User <-> Books)
user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    group: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_librarian: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    borrowed_books: Mapped[list["Borrowing"]] = relationship(
        "Borrowing",
        foreign_keys="Borrowing.user_id",
        back_populates="user"
    )

    favorites: Mapped[List["Books"]] = relationship(
        "Books",
        secondary=user_favorites,
        back_populates="favorited_by"
    )
