import mimetypes, os, glob, io, tempfile
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from ..services import audit as audit_svc
from ..services import cifratura
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from PIL import Image as PILImage
from ..database import get_db
from ..models.certificato_template import CertificatoTemplate
from ..models.corso import Corso
from ..services.certificati import CAMPI_DISPONIBILI, genera_pdf_da_template, valida_campo
from .deps import require_training_admin

router = APIRouter(prefix="/api/certificato-templates", tags=["certificato-templates"])

TEMPLATE_DIR = "/app/uploads/template_attestati"
ESTENSIONI = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

IMMAGINE_MAX_BYTE = 10 * 1024 * 1024
IMMAGINE_MAX_PIXEL = 40_000_000


def _id_template(template_id: str) -> str:
    try:
        return str(UUID(template_id))
    except ValueError:
        raise HTTPException(404)  # un identificativo che non e' un UUID non puo' esistere (e non deve arrivare al database ne' al nome del file)


class TemplateIn(BaseModel):
    nome: str

class TemplateUpdate(BaseModel):
    nome: Optional[str] = None
    campi: Optional[List[Dict[str, Any]]] = None
    is_default: Optional[bool] = None

def _serialize(t: CertificatoTemplate):
    return {
        "id": str(t.id), "nome": t.nome,
        "immagine_url": f"/certificato-templates/{t.id}/immagine?v={int(os.path.getmtime(t.immagine_path))}" if t.immagine_path and os.path.exists(t.immagine_path) else None,
        "larghezza_px": t.larghezza_px, "altezza_px": t.altezza_px,
        "campi": t.campi or [], "is_default": t.is_default,
    }

@router.get("/campi-disponibili")
def campi_disponibili(user=Depends(require_training_admin)):
    return CAMPI_DISPONIBILI

@router.get("")
def list_templates(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    return [_serialize(t) for t in db.query(CertificatoTemplate).order_by(CertificatoTemplate.created_at).all()]

@router.post("")
def create_template(data: TemplateIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    t = CertificatoTemplate(nome=data.nome, campi=[])
    db.add(t); db.flush()
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="certificato_template", entity_id=str(t.id), entity_name=t.nome)
    db.commit(); db.refresh(t)
    return _serialize(t)

@router.post("/{template_id}/immagine")
def upload_immagine(template_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_training_admin)):
    template_id = _id_template(template_id)
    t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    estensione = ESTENSIONI.get(file.content_type)
    if not estensione:
        raise HTTPException(400, "Formato non supportato: usa PNG, JPG o WEBP")
    contenuto = file.file.read(IMMAGINE_MAX_BYTE + 1)
    if len(contenuto) > IMMAGINE_MAX_BYTE:
        raise HTTPException(400, "Il file è troppo grande (massimo 10 MB)")
    try:  # l'immagine si controlla PRIMA di toccare lo sfondo che c'e' gia'
        with PILImage.open(io.BytesIO(contenuto)) as img:
            larghezza, altezza = img.size
            if larghezza * altezza > IMMAGINE_MAX_PIXEL:
                raise ValueError("troppi pixel")
            img.load()
    except Exception:
        raise HTTPException(400, "Immagine non valida o troppo grande (massimo 10 MB e 40 megapixel)")
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    for vecchio in glob.glob(os.path.join(TEMPLATE_DIR, f"{template_id}.*")):
        os.remove(vecchio)
    path = os.path.join(TEMPLATE_DIR, f"{template_id}{estensione}")
    cifratura.scrivi_file(path, contenuto)
    t.immagine_path = path
    t.larghezza_px = larghezza
    t.altezza_px = altezza
    db.commit()
    return _serialize(t)

@router.put("/{template_id}")
def update_template(template_id: str, data: TemplateUpdate, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    template_id = _id_template(template_id)
    t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    if data.nome is not None:
        t.nome = data.nome
    if data.campi is not None:
        chiavi_valide = {c["chiave"] for c in CAMPI_DISPONIBILI}
        for campo in data.campi:
            if campo.get("chiave") not in chiavi_valide:
                raise HTTPException(400, f"Campo non valido: {campo.get('chiave')}")
            try:
                valida_campo(campo)
            except ValueError as err:
                raise HTTPException(400, str(err))
        t.campi = data.campi
    if data.is_default is not None:
        if data.is_default:
            db.query(CertificatoTemplate).filter(CertificatoTemplate.id != t.id).update({"is_default": False})
            t.is_default = True
        else:
            t.is_default = False
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="certificato_template", entity_id=str(t.id), entity_name=t.nome)
    db.commit()
    return _serialize(t)

@router.get("/{template_id}/anteprima.pdf")
def anteprima(template_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    template_id = _id_template(template_id)
    t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    if not t.immagine_path:
        raise HTTPException(400, "Carica prima un'immagine di sfondo")
    valori = {
        "nome_discente": "Nome Cognome di esempio", "titolo_corso": "Titolo del corso di esempio",
        "data_evento": datetime.utcnow().strftime("%d/%m/%Y"), "ore_corso": "8",
        "azienda_nome": "Azienda S.r.l.", "ente_erogatore": "Ente formativo di esempio",
        "docente_nome": "Nome Docente", "codice_verifica": "ABCD1234EFGH5678",
    }
    with tempfile.TemporaryDirectory() as cartella:  # file temporaneo proprio di questa richiesta
        path = os.path.join(cartella, "anteprima.pdf")
        genera_pdf_da_template(path, template=t, valori=valori)
        contenuto = cifratura.leggi_file(path)
    return Response(content=contenuto, media_type="application/pdf")

@router.get("/{template_id}/immagine")
def immagine_template(template_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    template_id = _id_template(template_id)
    t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == template_id).first()
    if not t or not t.immagine_path or not os.path.exists(t.immagine_path):
        raise HTTPException(404)
    return Response(cifratura.leggi_file(t.immagine_path), media_type=mimetypes.guess_type(t.immagine_path)[0] or "application/octet-stream",
                    headers={"Cache-Control": "private, no-store"})


@router.delete("/{template_id}")
def delete_template(template_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    template_id = _id_template(template_id)
    t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    in_uso = db.query(Corso).filter(Corso.certificato_template_id == t.id).count()
    if in_uso:
        raise HTTPException(400, f"Template assegnato a {in_uso} corso(i): rimuovi l'assegnazione prima di eliminarlo")
    for vecchio in glob.glob(os.path.join(TEMPLATE_DIR, f"{template_id}.*")):
        os.remove(vecchio)
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="certificato_template", entity_id=str(t.id), entity_name=t.nome)
    db.delete(t)
    db.commit()
    return {"ok": True}
