from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
import os

from .database import engine, Base, SessionLocal
from .models import (
    user, group, azienda, organizzazione, corso, percorso, edizione,
    iscrizione, evidenza, video, test, certificato, notification, audit,
)
from .api import (
    setup, auth, groups, organizzazioni, azienda as azienda_api,
    corsi, percorsi, edizioni, evidenze, certificati, notifications,
    test as test_api, gradimenti, video as video_api,
)
from .services.notifiche import genera_notifiche

app = FastAPI(title="Piattaforma E-Learning", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])

scheduler = BackgroundScheduler()

def _job_genera_notifiche():
    db = SessionLocal()
    try:
        genera_notifiche(db)
    finally:
        db.close()

@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(_job_genera_notifiche, "interval", hours=24, id="notifiche_giornaliere", replace_existing=True)
    scheduler.start()
    print("[startup] DB OK, scheduler notifiche avviato")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)

os.makedirs("/app/uploads/certificati", exist_ok=True)
os.makedirs("/app/uploads/attestati_esterni", exist_ok=True)
os.makedirs("/app/videos/originali", exist_ok=True)
os.makedirs("/app/videos/pronti", exist_ok=True)
os.makedirs("/app/videos/sottotitoli", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
app.mount("/videos", StaticFiles(directory="/app/videos"), name="videos")

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(organizzazioni.router)
app.include_router(azienda_api.router)
app.include_router(corsi.router)
app.include_router(percorsi.router)
app.include_router(edizioni.router)
app.include_router(evidenze.router)
app.include_router(certificati.router)
app.include_router(notifications.router)
app.include_router(test_api.router)
app.include_router(gradimenti.router)
app.include_router(video_api.router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
