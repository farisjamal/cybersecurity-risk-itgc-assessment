"""Create the initial Example Bank Lab schema.

Revision ID: 20260925_0001
Revises: None
"""

from __future__ import annotations

from alembic import op

from bank_lab import models as bank_models  # noqa: F401
from bank_lab.database import Base

revision = "20260925_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the versioned baseline schema on a fresh database."""

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the fresh baseline schema for local/test rollback only."""

    Base.metadata.drop_all(bind=op.get_bind())
