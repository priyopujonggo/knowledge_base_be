from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=True)  # nullable untuk social login
    avatar_url: Mapped[str] = mapped_column(String, nullable=True)

    # Social login
    google_id: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    github_id: Mapped[str] = mapped_column(String, nullable=True, unique=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
    DateTime(timezone=True), 
    nullable=True,
    onupdate=func.now()
)

    documents: Mapped[list["Document"]] = relationship("Document", back_populates="owner")