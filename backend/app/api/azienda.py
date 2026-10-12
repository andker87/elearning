import os, glob, io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from ..database import get_db
from ..config import settings
from ..models.azienda import Azienda
from ..services.email import invia_email
from ..services import audit as audit_svc
from .deps import require_admin_tecnico

router = APIRouter(prefix="/api/azienda", tags=["azienda"])

LOGO_DIR = "/app/uploads/azienda"
LOGO_ESTENSIONI = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

class AziendaIn(BaseModel):
    ragione_sociale: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = "IT"
    email: Optional[str] = None
    pec: Optional[str] = None

class PiattaformaIn(BaseModel):
    nome_piattaforma: Optional[str] = None
    url_pubblico: Optional[str] = None

class SmtpTest(BaseModel):
    destinatario: str

def _get_or_create(db: Session) -> Azienda:
    a = db.query(Azienda).first()
    if not a:
        a = Azienda()
        db.add(a); db.commit(); db.refresh(a)
    return a

def _serialize(a: Azienda):
    data = {c.name: getattr(a, c.name) for c in a.__table__.columns
            if c.name not in ("vapid_private_key", "vapid_public_key")}
    # Lo SMTP si configura solo a livello di ambiente/container (vedi
    # config.py) - qui si espone solo lo stato, mai credenziali: chi
    # amministra la piattaforma via UI (Admin tecnico) lo vede attivo o
    # no, ma non può modificarlo. Stesso schema previsto per una futura SSO.
    data["smtp"] = {
        "configurato": settings.smtp_enabled,
        "host": settings.SMTP_HOST,
        "porta": settings.SMTP_PORT,
        "mittente": settings.SMTP_MITTENTE,
        "tls": settings.SMTP_TLS,
    }
    data["logo_url"] = a.logo_path.replace("/app/uploads", "/uploads") if a.logo_path else None
    data["icona_url"] = a.icona_path.replace("/app/uploads", "/uploads") if a.icona_path else None
    return data

def nome_piattaforma(a: Optional[Azienda]) -> str:
    return (a.nome_piattaforma or "").strip() or "E-Learning" if a else "E-Learning"

@router.get("/pubblica")
def info_pubblica(db: Session = Depends(get_db)):
    """Marchio e nome mostrati prima del login (schermata di accesso, titolo
    della pagina): niente di riservato, solo cio' che l'utente gia' vede."""
    a = db.query(Azienda).first()
    return {
        "nome_piattaforma": nome_piattaforma(a),
        "nome_azienda": a.ragione_sociale if a else None,
        "logo_url": a.logo_path.replace("/app/uploads", "/uploads") if a and a.logo_path else None,
    }

@router.get("/manifest.json")
def manifest(db: Session = Depends(get_db)):
    """Manifest dell'app installabile generato dalle impostazioni (nome e
    icona), invece di un file statico che andrebbe modificato a mano."""
    nome = nome_piattaforma(db.query(Azienda).first())
    icone = [{"src": f"/api/azienda/icona?size={s}", "type": "image/png", "sizes": f"{s}x{s}", **({"purpose": p} if p else {})}
             for p in (None, "maskable") for s in (192, 512)]
    corpo = {"short_name": nome[:12], "name": nome, "icons": icone, "start_url": "/", "scope": "/",
             "display": "standalone", "theme_color": "#0E7C66", "background_color": "#FAFBFC"}
    import json
    return Response(content=json.dumps(corpo), media_type="application/manifest+json")

@router.put("/piattaforma")
def update_piattaforma(data: PiattaformaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _get_or_create(db)
    nome = (data.nome_piattaforma or "").strip()
    if len(nome) > 60:
        raise HTTPException(400, "Il nome della piattaforma e' troppo lungo (massimo 60 caratteri)")
    url = (data.url_pubblico or "").strip().rstrip("/")
    if url and not (url.lower().startswith("https://") or url.lower().startswith("http://")):
        raise HTTPException(400, "L'URL pubblico deve iniziare con http:// o https://")
    a.nome_piattaforma = nome or None
    a.url_pubblico = url or None
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Impostazioni piattaforma",
                                detail=f"nome: {nome or '(predefinito)'} - url: {url or '(non impostato)'}")
    db.commit()
    return _serialize(a)

@router.post("/icona")
def upload_icona(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    estensione = LOGO_ESTENSIONI.get(file.content_type)
    if not estensione:
        raise HTTPException(400, "Formato non supportato: usa PNG, JPG o WEBP")
    contenuto = file.file.read()
    try:
        img = Image.open(io.BytesIO(contenuto))
        larghezza, altezza = img.size
    except Exception:
        raise HTTPException(400, "Immagine non valida")
    if min(larghezza, altezza) < 192:
        raise HTTPException(400, "L'icona deve essere almeno 192x192 pixel (meglio 512x512, quadrata)")
    a = _get_or_create(db)
    os.makedirs(LOGO_DIR, exist_ok=True)
    for vecchio in glob.glob(os.path.join(LOGO_DIR, "icona.*")):
        os.remove(vecchio)
    path = os.path.join(LOGO_DIR, f"icona{estensione}")
    with open(path, "wb") as f:
        f.write(contenuto)
    a.icona_path = path
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Icona dell'app", detail="caricata")
    db.commit()
    return _serialize(a)

@router.delete("/icona")
def elimina_icona(request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _get_or_create(db)
    for vecchio in glob.glob(os.path.join(LOGO_DIR, "icona.*")):
        os.remove(vecchio)
    a.icona_path = None
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="azienda", entity_name="Icona dell'app")
    db.commit()
    return _serialize(a)

@router.get("")
def get_azienda(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    return _serialize(_get_or_create(db))

@router.put("")
def update_azienda(data: AziendaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _get_or_create(db)
    for k, v in data.model_dump().items():
        setattr(a, k, v)
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Dati aziendali")
    db.commit()
    return _serialize(a)

@router.post("/logo")
def upload_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    estensione = LOGO_ESTENSIONI.get(file.content_type)
    if not estensione:
        raise HTTPException(400, "Formato non supportato: usa PNG, JPG o WEBP")
    contenuto = file.file.read()
    try:  # il tipo dichiarato dal browser non basta: deve essere davvero un'immagine
        Image.open(io.BytesIO(contenuto)).verify()
    except Exception:
        raise HTTPException(400, "Il file non è un'immagine valida")
    a = _get_or_create(db)
    os.makedirs(LOGO_DIR, exist_ok=True)
    for vecchio in glob.glob(os.path.join(LOGO_DIR, "logo.*")):
        os.remove(vecchio)
    path = os.path.join(LOGO_DIR, f"logo{estensione}")
    with open(path, "wb") as f:
        f.write(contenuto)
    a.logo_path = path
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Logo aziendale", detail="caricato")
    db.commit()
    return _serialize(a)

@router.delete("/logo")
def elimina_logo(request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _get_or_create(db)
    for vecchio in glob.glob(os.path.join(LOGO_DIR, "logo.*")):
        os.remove(vecchio)
    a.logo_path = None
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="azienda", entity_name="Logo aziendale")
    db.commit()
    return _serialize(a)

@router.get("/icona")
def icona(size: int = Query(192), db: Session = Depends(get_db)):
    """Icona per il manifest PWA (installazione su telefono/desktop) - niente
    autenticazione: il browser la scarica da solo, come il manifest stesso.
    Usa il logo aziendale se caricato (quadrato su sfondo bianco), altrimenti
    lo stesso marchio "EL" già usato nella sidebar."""
    dim = max(32, min(512, size))
    a = db.query(Azienda).first()
    sorgente_path = next((p for p in (a.icona_path if a else None, a.logo_path if a else None) if p and os.path.exists(p)), None)
    quadro = None
    if sorgente_path:
        try:
            sorgente = Image.open(sorgente_path).convert("RGBA")
            lato = max(sorgente.size)
            quadro = Image.new("RGBA", (lato, lato), (255, 255, 255, 255))
            quadro.paste(sorgente, ((lato - sorgente.size[0]) // 2, (lato - sorgente.size[1]) // 2), sorgente)
            quadro = quadro.resize((dim, dim), Image.LANCZOS)
        except Exception:
            quadro = None  # file rovinato: si ripiega sul marchio, l'icona non deve mai rompere l'app
    if quadro is None:
        quadro = Image.new("RGBA", (dim, dim), (14, 124, 102, 255))
        disegno = ImageDraw.Draw(quadro)
        testo = "EL"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(dim * 0.42))
        except Exception:
            font = ImageFont.load_default()
        box = disegno.textbbox((0, 0), testo, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        disegno.text(((dim - tw) / 2 - box[0], (dim - th) / 2 - box[1]), testo, fill="white", font=font)
    buf = io.BytesIO()
    quadro.convert("RGB").save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@router.post("/smtp/test")
def test_smtp(data: SmtpTest, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    if not settings.smtp_enabled:
        raise HTTPException(400, "SMTP non configurato in ambiente")
    ok = invia_email(data.destinatario, "Email di prova", "Questa è un'email di prova dalla piattaforma formazione.")
    if not ok:
        raise HTTPException(400, "Invio fallito: controlla i parametri SMTP in ambiente e i log del backend")
    audit_svc.log_from_request(db, request, user, "SMTP_TEST", entity_type="azienda", entity_name="Test SMTP", detail=f"destinatario: {data.destinatario}")
    db.commit()
    return {"ok": True}
