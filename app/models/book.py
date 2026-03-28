from datetime import datetime
from enum import Enum as PyEnum
from typing import List

from sqlalchemy import ForeignKey, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Books(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_number: Mapped[str] = mapped_column()
    title: Mapped[str] = mapped_column()
    author: Mapped[str] = mapped_column()
    year: Mapped[int] = mapped_column()
    country: Mapped[str] = mapped_column()
    pages: Mapped[int] = mapped_column()

    favorited_by: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_favorites",
        back_populates="favorites"
    )


class BorrowingStatus(PyEnum):
    PENDING = "pending"  # Забронировано (книга еще в библиотеке)
    ISSUED = "issued"  # Выдано (книга у студента)
    RETURNED = "returned"  # Вернули обратно
    CANCELLED = "cancelled"  # Студент передумал или не пришел
    OVERDUE = "overdue"  # Просрочено (не забрали вовремя или не вернули вовремя)


class Borrowing(Base):
    __tablename__ = "borrowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))

    # Кто выдал/принял книгу
    librarian_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Текущее состояние
    status: Mapped[BorrowingStatus] = mapped_column(
        Enum(BorrowingStatus),
        default=BorrowingStatus.PENDING
    )

    # Таймстампы
    reserved_at: Mapped[datetime] = mapped_column(server_default=func.now())  # Дата брони
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)  # Дата выдачи в руки
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)  # Дедлайн
    returned_at: Mapped[datetime | None] = mapped_column(nullable=True)  # Когда вернули

    # Отношения
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="borrowed_books")
    librarian: Mapped["User | None"] = relationship("User", foreign_keys=[librarian_id])
    book: Mapped["Books"] = relationship()