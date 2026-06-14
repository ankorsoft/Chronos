"""initial schema

Revision ID: 3faacbccf5bb
Revises: 
Create Date: 2026-06-14 10:59:02.758388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel


# revision identifiers, used by Alembic.
revision: str = '3faacbccf5bb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create all tables from SQLModel metadata
    from app.models import Project, ProjectSnapshot, ProjectExport  # noqa: F401
    SQLModel.metadata.create_all(op.get_bind())


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('projectexport')
    op.drop_table('projectsnapshot')
    op.drop_table('project')