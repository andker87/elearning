from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict
from ..database import get_db
from ..models.group import Group
from .deps import require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/groups", tags=["groups"])

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#5a6b8a"
    permissions: Dict[str, str] = {}
    parent_id: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    permissions: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    parent_id: Optional[str] = None

def _serialize(g: Group):
    return {"id": str(g.id), "name": g.name, "description": g.description, "color": g.color,
            "permissions": g.permissions, "is_system": g.is_system, "is_active": g.is_active,
            "parent_id": str(g.parent_id) if g.parent_id else None}

@router.get("")
def list_groups(db: Session = Depends(get_db), user=Depends(get_current_user)):
    groups = db.query(Group).order_by(Group.sort_order).all()
    return [_serialize(g) for g in groups]

@router.post("")
def create_group(data: GroupCreate, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = Group(name=data.name, description=data.description, color=data.color,
              permissions=data.permissions, parent_id=data.parent_id or None)
    db.add(g); db.commit(); db.refresh(g)
    return _serialize(g)

@router.put("/{group_id}")
def update_group(group_id: str, data: GroupUpdate, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g: raise HTTPException(404)
    # I Ruoli di sistema sono rinominabili ma non modificabili nei permessi/gerarchia.
    if g.is_system and (data.permissions is not None or data.parent_id is not None):
        raise HTTPException(400, "I Ruoli di sistema non hanno permessi o gerarchia personalizzabili")
    for field in ("name", "description", "color", "is_active"):
        val = getattr(data, field)
        if val is not None: setattr(g, field, val)
    if not g.is_system:
        if data.permissions is not None: g.permissions = data.permissions
        if data.parent_id is not None: g.parent_id = data.parent_id or None
    db.commit()
    return _serialize(g)

@router.delete("/{group_id}")
def delete_group(group_id: str, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g: raise HTTPException(404)
    if g.is_system: raise HTTPException(400, "I Ruoli di sistema non sono eliminabili")
    db.query(Group).filter(Group.parent_id == group_id).update({"parent_id": None})
    db.delete(g); db.commit()
    return {"ok": True}
