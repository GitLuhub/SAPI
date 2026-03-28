from typing import Optional
from sqlalchemy.orm import Session

from app.db.models.extracted_data import AuditLog


def log_action(
    db: Session,
    action: str,
    user_id=None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Inserts an AuditLog entry. The caller is responsible for db.commit()."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
