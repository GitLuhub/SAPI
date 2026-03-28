"""Add performance indexes

Revision ID: 002_add_indexes
Revises: 001_initial
Create Date: 2026-03-28 00:00:00.000000

Índices añadidos:
- documents.created_at       — filtros de fecha en GET /documents/
- extracted_data (document_id, field_name) UNIQUE — upsert en el worker
- audit_logs.entity_id       — búsqueda de audit por entidad
- audit_logs.action          — filtrado por tipo de acción
"""
from typing import Sequence, Union
from alembic import op


revision: str = '002_add_indexes'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # documents: filtrado por fecha de carga
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])

    # extracted_data: garantiza un único campo por documento + acelera upserts
    op.create_index(
        'uq_extracted_data_document_field',
        'extracted_data',
        ['document_id', 'field_name'],
        unique=True,
    )

    # audit_logs: búsqueda por entidad y por tipo de acción
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity_id', table_name='audit_logs')
    op.drop_index('uq_extracted_data_document_field', table_name='extracted_data')
    op.drop_index('ix_documents_created_at', table_name='documents')
