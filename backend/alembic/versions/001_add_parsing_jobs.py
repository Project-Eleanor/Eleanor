"""Add parsing_jobs table

Revision ID: 001
Revises:
Create Date: 2024-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create parsing_jobs table
    op.create_table(
        'parsing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('evidence_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('parser_type', sa.String(100), nullable=False),
        sa.Column('parser_hint', sa.String(100), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'pending', 'queued', 'running', 'completed', 'failed', 'cancelled',
                name='parsingjobstatus'
            ),
            nullable=False,
            server_default='pending'
        ),
        sa.Column('events_parsed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('events_indexed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('events_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('results_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('submitted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_parsing_jobs_evidence_id', 'parsing_jobs', ['evidence_id'])
    op.create_index('ix_parsing_jobs_case_id', 'parsing_jobs', ['case_id'])
    op.create_index('ix_parsing_jobs_status', 'parsing_jobs', ['status'])
    op.create_index('ix_parsing_jobs_celery_task_id', 'parsing_jobs', ['celery_task_id'])


def downgrade() -> None:
    op.drop_index('ix_parsing_jobs_celery_task_id', table_name='parsing_jobs')
    op.drop_index('ix_parsing_jobs_status', table_name='parsing_jobs')
    op.drop_index('ix_parsing_jobs_case_id', table_name='parsing_jobs')
    op.drop_index('ix_parsing_jobs_evidence_id', table_name='parsing_jobs')
    op.drop_table('parsing_jobs')
    op.execute("DROP TYPE IF EXISTS parsingjobstatus")
