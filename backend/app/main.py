import mimetypes
from fastapi import HTTPException, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import DataError
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
import os

from .database import engine, Base, SessionLocal
from .models import (
    user, group, azienda, organizzazione, corso, percorso, edizione,
    iscrizione, evidenza, video, test, certificato, certificato_template,
    notification, audit, richiesta_corso, fabbisogno, autoiscrizione,
    push_subscription, comunicazione_edizione, job_run, password_reset, etichetta, mansione,
)
from .api import (
    setup, auth, groups, mansioni, organizzazioni, azienda as azienda_api,
    corsi, percorsi, edizioni, evidenze, certificati, certificato_templates,
    notifications, test as test_api, gradimenti, video as video_api,
    richieste_corso, fabbisogno as fabbisogno_api, autoiscrizione as autoiscrizione_api,
    registro, dashboard_formazione, dashboard_kpi, push as push_api,
    calendario as calendario_api, admin_tecnico as admin_tecnico_api,
    entra_sync as entra_sync_api, sso as sso_api, about as about_api, privacy as privacy_api, password_reset as password_reset_api, matrice_ispezione as matrice_api, configurazione as configurazione_api, etichette as etichette_api,
)
from .config import settings
from .services import cifratura
from .services.notifiche import genera_notifiche
from .services.job_tracking import esegui_tracciato
from .migrazioni import esegui_migrazioni

def _controlla_cifratura():
    from .services.cifratura_ops import controlla_avvio
    db = SessionLocal()
    try:
        controlla_avvio(db)   # si ferma con un messaggio chiaro se chiave mancante o sbagliata
        from .services.impronte import assicura
        assicura()            # chiave per cercare i dati personali cifrati: creata al primo avvio
    finally:
        db.close()

def _recupera_video():
    from .services.video_elaborazione import recupera_interrotti
    db = SessionLocal()
    try:
        recupera_interrotti(db)   # video rimasti a meta' per un riavvio; elimina gli originali in chiaro
    finally:
        db.close()

def _ensure_vapid_keys():
    """Le chiavi VAPID (notifiche push, RFC 8292) le genera la piattaforma
    stessa al primo avvio, una sola volta - non sono credenziali di terze
    parti come SMTP, restano nel DB (vedi models/azienda.py)."""
    from .models.azienda import Azienda
    db = SessionLocal()
    try:
        a = db.query(Azienda).first()
        if not a:
            a = Azienda()
            db.add(a); db.flush()
        if not a.vapid_private_key:
            from py_vapid import Vapid01
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            import base64
            v = Vapid01()
            v.generate_keys()
            raw_pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
            a.vapid_private_key = cifratura.cifra_testo(v.private_pem().decode())
            a.vapid_public_key = base64.urlsafe_b64encode(raw_pub).decode().rstrip("=")
            db.commit()
            print("[startup] chiavi VAPID generate per le notifiche push")
        elif cifratura.attiva() and not cifratura.testo_con_chiave_corrente(a.vapid_private_key):
            a.vapid_private_key = cifratura.cifra_testo(cifratura.decifra_testo(a.vapid_private_key))   # cifra o ricifra con la chiave corrente
            db.commit()
    finally:
        db.close()

app = FastAPI(title="Piattaforma E-Learning", version="0.1.0")
# Sito e API passano dallo stesso indirizzo (nginx): CORS non serve e di default non ammette nessun altro sito.
# Per ammettere altri indirizzi: CORS_ORIGINS="https://uno.example,https://due.example" (solo da ambiente).
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_lista, allow_credentials=False,
                    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])

@app.exception_handler(cifratura.ErroreCifratura)
async def errore_cifratura(request: Request, exc: cifratura.ErroreCifratura):
    return JSONResponse(status_code=503, content={"detail": "Dati cifrati non leggibili: controlla CHIAVE_CIFRATURA (vedi docs/sicurezza.md)"})

scheduler = BackgroundScheduler()

def _job_genera_notifiche():
    esegui_tracciato("notifiche_giornaliere", genera_notifiche)

def _ensure_etichette():
    from .services.etichette import crea_famiglie_iniziali
    db = SessionLocal()
    try:
        crea_famiglie_iniziali(db)
    finally:
        db.close()

def _job_rinnovi_automatici():
    from .services.rinnovo import esegui_rinnovi
    esegui_tracciato("rinnovi_automatici", esegui_rinnovi)

def _job_manutenzione_audit():
    from .services.audit_manutenzione import manutenzione
    esegui_tracciato("manutenzione_audit", manutenzione)

def _job_sync_entra():
    from .services.entra_sync import sincronizza_automatico
    esegui_tracciato("sync_entra", sincronizza_automatico)

@app.on_event("startup")
async def startup():
    esegui_migrazioni()
    _controlla_cifratura()
    _recupera_video()
    _ensure_vapid_keys()
    _ensure_etichette()
    scheduler.add_job(_job_genera_notifiche, "interval", hours=24, id="notifiche_giornaliere", replace_existing=True)
    scheduler.add_job(_job_rinnovi_automatici, "cron", hour=2, minute=0, id="rinnovi_automatici", replace_existing=True)
    scheduler.add_job(_job_manutenzione_audit, "cron", hour=3, minute=0, id="manutenzione_audit", replace_existing=True)
    if settings.entra_sync_enabled and settings.ENTRA_SYNC_AUTO:
        scheduler.add_job(_job_sync_entra, "cron", hour=2, minute=30, id="sync_entra", replace_existing=True)
    scheduler.start()
    print("[startup] DB OK, scheduler notifiche avviato")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)

os.makedirs("/app/uploads/certificati", exist_ok=True)
os.makedirs("/app/uploads/attestati_esterni", exist_ok=True)
os.makedirs("/app/uploads/azienda", exist_ok=True)
os.makedirs("/app/uploads/template_attestati", exist_ok=True)
os.makedirs("/app/videos/originali", exist_ok=True)
os.makedirs("/app/videos/pronti", exist_ok=True)
os.makedirs("/app/videos/sottotitoli", exist_ok=True)


# Dei file caricati sono pubblici solo logo e icona (servono alla pagina di login e all'app installata).
# Attestati, allegati, template e informativa si scaricano solo dalle rotte con autenticazione.
# I file possono essere cifrati su disco: qui si decifrano al volo.
PUBBLICI = ("logo.", "icona.")


@app.get("/uploads/azienda/{nome}")
def file_pubblico(nome: str):
    if "/" in nome or "\\" in nome or ".." in nome or not nome.startswith(PUBBLICI):
        raise HTTPException(404)
    percorso = os.path.join("/app/uploads/azienda", nome)
    if not os.path.isfile(percorso):
        raise HTTPException(404)
    return Response(cifratura.leggi_file(percorso), media_type=mimetypes.guess_type(nome)[0] or "application/octet-stream",
                    headers={"Cache-Control": "public, max-age=300"})


@app.get("/uploads/{percorso:path}")
def altri_file_non_pubblici(percorso: str):
    raise HTTPException(404)

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(mansioni.router)
app.include_router(organizzazioni.router)
app.include_router(azienda_api.router)
app.include_router(corsi.router)
app.include_router(percorsi.router)
app.include_router(edizioni.router)
app.include_router(evidenze.router)
app.include_router(certificati.router)
app.include_router(certificato_templates.router)
app.include_router(notifications.router)
app.include_router(test_api.router)
app.include_router(gradimenti.router)
app.include_router(video_api.router)
app.include_router(richieste_corso.router)
app.include_router(fabbisogno_api.router)
app.include_router(autoiscrizione_api.router)
app.include_router(registro.router)
app.include_router(dashboard_formazione.router)
app.include_router(dashboard_kpi.router)
app.include_router(push_api.router)
app.include_router(calendario_api.router)
app.include_router(admin_tecnico_api.router)
app.include_router(sso_api.router)
app.include_router(about_api.router)
app.include_router(privacy_api.router)
app.include_router(password_reset_api.router)
app.include_router(entra_sync_api.router)
app.include_router(matrice_api.router)
app.include_router(configurazione_api.router)
app.include_router(etichette_api.router)

@app.exception_handler(DataError)
async def dato_rifiutato_dal_database(request: Request, exc: DataError):
    """Un identificativo che non e' un UUID (o un valore fuori misura) arriva al database e darebbe errore 500:
    e' un errore di chi chiama, non del server."""
    if "uuid" in str(exc.orig).lower():
        return JSONResponse({"detail": "Identificativo non valido"}, status_code=404)
    return JSONResponse({"detail": "Dati non validi"}, status_code=400)


@app.get("/api/health")
def health():
    return {"status": "ok"}
