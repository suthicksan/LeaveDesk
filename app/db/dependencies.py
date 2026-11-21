
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    # Create a new database session
    db = SessionLocal()

    try:
        # Provide the session to the API endpoint
        yield db
    finally:
        # Always close the session after the request
        db.close()
