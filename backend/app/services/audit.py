from sqlalchemy.orm import Session
from fastapi import Request
from ..models.audit import AuditLog

def log_from_request(db: Session, request: Request, user, action: str,
                      entity_type: str = None, entity_id: str = None,
                      entity_name: str = None, detail: str = None):
    entry = AuditLog(
        user_id=getattr(user, "id", None),
        user_email=getattr(user, "email", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        detail=detail,
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(entry)
    db.flush()
