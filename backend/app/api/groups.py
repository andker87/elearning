from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.fabbisogno import FabbisognoCampagnaInvito, FabbisognoRichiesta
from ..models.group import Group, UserGroup
from ..models.percorso import PercorsoFormativo
from ..services import audit as audit_svc
from .deps import require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/groups", tags=["groups"])

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#5a6b8a"
    parent_id: Optional[str] = None
    responsabile_id: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    parent_id: Optional[str] = None
    responsabile_id: Optional[str] = None

def _serialize(g: Group):
    return {"id": str(g.id), "name": g.name, "description": g.description, "color": g.color,
            "is_active": g.is_active,
            "parent_id": str(g.parent_id) if g.parent_id else None,
            "responsabile_id": str(g.responsabile_id) if g.responsabile_id else None,
            "responsabile_nome": g.responsabile.full_name if g.responsabile else None}

@router.get("")
def list_groups(db: Session = Depends(get_db), user=Depends(get_current_user)):
    groups = db.query(Group).order_by(Group.sort_order).all()
    return [_serialize(g) for g in groups]

@router.post("")
def create_group(data: GroupCreate, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = Group(name=data.name, description=data.description, color=data.color,
              parent_id=data.parent_id or None, is_ufficio=True, responsabile_id=data.responsabile_id or None)
    db.add(g); db.flush()
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="group", entity_id=str(g.id), entity_name=g.name)
    db.commit(); db.refresh(g)
    return _serialize(g)

@router.put("/{group_id}")
def update_group(group_id: str, data: GroupUpdate, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g: raise HTTPException(404)
    for field in ("name", "description", "color", "is_active"):
        val = getattr(data, field)
        if val is not None: setattr(g, field, val)
    if data.parent_id:
        _verifica_nessun_ciclo(db, g.id, data.parent_id)
    if data.parent_id is not None: g.parent_id = data.parent_id or None
    if data.responsabile_id is not None: g.responsabile_id = data.responsabile_id or None
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="group", entity_id=str(g.id), entity_name=g.name)
    db.commit()
    return _serialize(g)

def _verifica_nessun_ciclo(db: Session, group_id, parent_id):
    """Un gruppo non puo' stare sotto se stesso ne' sotto uno dei suoi sotto-gruppi: la gerarchia
    (responsabili, sotto-uffici) andrebbe in giro all'infinito."""
    corrente, visti = str(parent_id), set()
    while corrente and corrente not in visti:
        if corrente == str(group_id):
            raise HTTPException(400, "Un gruppo non può stare sotto se stesso o sotto uno dei suoi sotto-gruppi")
        visti.add(corrente)
        padre = db.query(Group.parent_id).filter(Group.id == corrente).scalar()
        corrente = str(padre) if padre else None

@router.delete("/{group_id}")
def delete_group(group_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g: raise HTTPException(404)
    if db.query(UserGroup).filter(UserGroup.group_id == g.id).first():
        raise HTTPException(400, "L'ufficio ha ancora persone: spostale in un altro ufficio prima di eliminarlo")
    if (db.query(PercorsoFormativo.id).filter(PercorsoFormativo.trigger_gruppo_id == g.id).first()
            or db.query(FabbisognoCampagnaInvito.id).filter(FabbisognoCampagnaInvito.ufficio_id == g.id).first()
            or db.query(FabbisognoRichiesta.id).filter((FabbisognoRichiesta.ufficio_origine_id == g.id)
                                                        | (FabbisognoRichiesta.ufficio_in_revisione_presso_id == g.id)).first()):
        raise HTTPException(400, "L'ufficio è ancora usato da un percorso (assegnazione automatica) o dal fabbisogno formativo: non si può eliminare")
    db.query(Group).filter(Group.parent_id == group_id).update({"parent_id": None})
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="group", entity_id=str(g.id), entity_name=g.name)
    db.delete(g); db.commit()
    return {"ok": True}
