"""add wiki tables

Revision ID: 0001_wiki
Revises: 91665c36ab05
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa

revision = '0001_wiki'
down_revision = '91665c36ab05'
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    """Check if a column exists in a table."""
    result = connection.execute(
        sa.text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl AND COLUMN_NAME = :col"
        ).bindparams(tbl=table, col=column)
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add wiki_config and indexing_strategy to collection (idempotent)
    if not _column_exists(conn, 'collection', 'wiki_config'):
        with op.batch_alter_table('collection') as batch_op:
            batch_op.add_column(sa.Column('wiki_config', sa.Text(), nullable=True))

    if not _column_exists(conn, 'collection', 'indexing_strategy'):
        with op.batch_alter_table('collection') as batch_op:
            batch_op.add_column(sa.Column('indexing_strategy', sa.Text(), nullable=True))

    # 2. Create wiki_pages table (skip if exists)
    try:
        op.create_table(
            'wiki_pages',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('collection_id', sa.String(24), nullable=False, index=True),
            sa.Column('user_id', sa.String(24), nullable=False, index=True),
            sa.Column('slug', sa.String(255), nullable=False),
            sa.Column('title', sa.String(512), nullable=False, server_default=''),
            sa.Column('page_type', sa.String(32), nullable=False, server_default='summary'),
            sa.Column('status', sa.String(32), nullable=False, server_default='published'),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('aliases', sa.JSON(), nullable=True),
            sa.Column('source_refs', sa.JSON(), nullable=True),
            sa.Column('chunk_refs', sa.JSON(), nullable=True),
            sa.Column('in_links', sa.JSON(), nullable=True),
            sa.Column('out_links', sa.JSON(), nullable=True),
            sa.Column('page_metadata', sa.JSON(), nullable=True),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('gmt_created', sa.DateTime(timezone=True), nullable=False),
            sa.Column('gmt_updated', sa.DateTime(timezone=True), nullable=False),
            sa.Column('gmt_deleted', sa.DateTime(timezone=True), nullable=True),
            sa.Index('idx_wiki_pages_collection_slug', 'collection_id', 'slug'),
            sa.Index('idx_wiki_pages_type', 'page_type'),
            sa.Index('idx_wiki_pages_status', 'status'),
        )
    except Exception:
        pass  # Table may already exist

    # 3. Create wiki_page_issues table
    try:
        op.create_table(
            'wiki_page_issues',
            sa.Column('id', sa.String(24), primary_key=True),
            sa.Column('collection_id', sa.String(24), nullable=False, index=True),
            sa.Column('user_id', sa.String(24), nullable=False),
            sa.Column('slug', sa.String(255), nullable=False, index=True),
            sa.Column('issue_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('suspected_collection_ids', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),
            sa.Column('reported_by', sa.String(100), nullable=False),
            sa.Column('gmt_created', sa.DateTime(timezone=True), nullable=False),
            sa.Column('gmt_updated', sa.DateTime(timezone=True), nullable=False),
            sa.Column('gmt_deleted', sa.DateTime(timezone=True), nullable=True),
            sa.Index('idx_wiki_issues_collection', 'collection_id'),
            sa.Index('idx_wiki_issues_status', 'status'),
        )
    except Exception:
        pass

    # 4. Create wiki_log_entries table
    try:
        op.create_table(
            'wiki_log_entries',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('collection_id', sa.String(24), nullable=False, index=True),
            sa.Column('action', sa.String(50), nullable=False),
            sa.Column('collection_ref', sa.String(36), nullable=True),
            sa.Column('doc_title', sa.String(255), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('pages_affected', sa.JSON(), nullable=True),
            sa.Column('gmt_created', sa.DateTime(timezone=True), nullable=False),
            sa.Index('idx_wiki_log_collection', 'collection_id'),
            sa.Index('idx_wiki_log_created', 'gmt_created'),
        )
    except Exception:
        pass


def downgrade() -> None:
    op.drop_table('wiki_log_entries')
    op.drop_table('wiki_page_issues')
    op.drop_table('wiki_pages')
    with op.batch_alter_table('collection') as batch_op:
        batch_op.drop_column('indexing_strategy')
        batch_op.drop_column('wiki_config')
