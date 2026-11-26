"""create initial database tables

Revision ID: fae365a3c28e
Revises:
"""

from alembic import op

from app.db.session import Base
from app.models.user import User
from app.models.leave import LeaveRequest
from app.models.wfh import WFHRequest

revision = "fae365a3c28e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all application tables."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Remove all application tables."""
    Base.metadata.drop_all(bind=op.get_bind())
