"""Add correlation states table and correlation_config field.

Revision ID: 003
Revises: 002
Create Date: 2025-01-26

This migration adds:
- correlation_config JSONB field to detection_rules table
- correlation_states table for tracking partial sequence matches
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add correlation_config column to detection_rules
    op.add_column(
        'detection_rules',
        sa.Column('correlation_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Create correlation_states table
    op.create_table(
        'correlation_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_key', sa.String(512), nullable=False),
        sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status',
            sa.Enum('active', 'completed', 'expired', name='correlationstatestatus'),
            nullable=False,
            server_default='active',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['rule_id'], ['detection_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_correlation_states_rule_id', 'correlation_states', ['rule_id'])
    op.create_index('ix_correlation_states_entity_key', 'correlation_states', ['entity_key'])
    op.create_index(
        'ix_correlation_states_rule_entity_status',
        'correlation_states',
        ['rule_id', 'entity_key', 'status'],
    )
    op.create_index(
        'ix_correlation_states_window_end',
        'correlation_states',
        ['window_end'],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_correlation_states_window_end', table_name='correlation_states')
    op.drop_index('ix_correlation_states_rule_entity_status', table_name='correlation_states')
    op.drop_index('ix_correlation_states_entity_key', table_name='correlation_states')
    op.drop_index('ix_correlation_states_rule_id', table_name='correlation_states')

    # Drop table
    op.drop_table('correlation_states')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS correlationstatestatus')

    # Remove column from detection_rules
    op.drop_column('detection_rules', 'correlation_config')
