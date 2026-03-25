from datetime import datetime, timedelta

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
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

class Borrowing(Base):
    __tablename__ = "borrowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    librarian_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    borrowed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    due_date: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now() + timedelta(days=settings.BORROWING_DAYS)
    )
    returned_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="borrowed_books")
    librarian: Mapped["User | None"] = relationship("User", foreign_keys=[librarian_id])
    book: Mapped["Books"] = relationship()