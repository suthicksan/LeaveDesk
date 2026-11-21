
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    # Database table name
    __tablename__ = "users"

    # Unique user ID
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # User's full name
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Each user must have a unique email
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    # Store the hashed password, never the original password
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Allowed values: manager or employee
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # References another user who is this user's manager.
    # Managers have manager_id = None.
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # Relationship to the manager
    manager: Mapped["User | None"] = relationship(
        "User",
        back_populates="team_members",
        remote_side="User.id"
    )

    # Relationship to employees reporting to this manager
    team_members: Mapped[list["User"]] = relationship(
        "User",
        back_populates="manager"
    )
