"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.Enum('admin', 'document_reviewer', 'user', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'document_types',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_types_id', 'document_types', ['id'])
    op.create_index('ix_document_types_name', 'document_types', ['name'], unique=True)

    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.String(length=50), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='UPLOADED'),
        sa.Column('upload_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('classification_confidence', sa.String(length=10), nullable=True),
        sa.Column('executive_summary', sa.String(length=2000), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_error', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_id', 'documents', ['id'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_upload_user_id', 'documents', ['upload_user_id'])
    op.create_index('ix_documents_document_type_id', 'documents', ['document_type_id'])
    op.create_foreign_key('fk_documents_upload_user', 'documents', 'users', ['upload_user_id'], ['id'])
    op.create_foreign_key('fk_documents_document_type', 'documents', 'document_types', ['document_type_id'], ['id'])

    op.create_table(
        'extracted_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('field_label', sa.String(length=200), nullable=True),
        sa.Column('ai_extracted_value', sa.String(length=1000), nullable=True),
        sa.Column('ai_confidence', sa.String(length=10), nullable=True),
        sa.Column('final_value', sa.String(length=1000), nullable=False),
        sa.Column('is_corrected', sa.Boolean(), nullable=False, default=False),
        sa.Column('corrected_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('corrected_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_extracted_data_id', 'extracted_data', ['id'])
    op.create_index('ix_extracted_data_document_id', 'extracted_data', ['document_id'])
    op.create_foreign_key('fk_extracted_data_document', 'extracted_data', 'documents', ['document_id'], ['id'], ondelete='CASCADE')

    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('details', sa.String(length=2000), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_foreign_key('fk_audit_logs_user', 'audit_logs', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('extracted_data')
    op.drop_table('documents')
    op.drop_table('document_types')
    op.drop_table('users')
