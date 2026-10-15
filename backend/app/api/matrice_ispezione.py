import csv
import io
import os
import re
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.azienda import Azienda
from ..models.certificato import Certificato
from ..models.corso import Corso
from ..models.evidenza import Evidenza
from ..models.group import Group, UserGroup
from ..models.percorso import PercorsoAssegnazione, PercorsoFormativo, PercorsoStep
from ..models.user import User
from ..services import audit as audit_svc
from ..services.export import neutralizza
from ..services.export import esporta, _a_excel, _a_pdf
from ..services.gerarchia import persone_ufficio_e_sottouffici
from .deps import require_training_admin
from .registro import _righe
from ..services.etichette import corsi_con_etichette, descrivi_filtro

router = APIRouter(prefix="/api/registro", tags=["registro"])

GIORNI_IN_SCADENZA = 30
MAX_FILE_PACCHETTO = 3000
MAX_RIGHE_PDF = 2000

# Quanto e' "buono" lo stato: tra piu' iscrizioni allo stesso corso conta la migliore.
ORDINE_STATI = ["valido", "in_scadenza", "in_corso", "da_aggiornare", "scaduto", "non_completato"]
ETICHETTE = {
    "valido": "Valido", "in_scadenza": "In scadenza", "in_corso": "In corso",
    "da_aggiornare": "Da aggiornare", "scaduto": "Scaduto", "non_completato": "Non completato", "mancante": "Mancante",
}


def _stato_cella(riga: dict, ora: datetime) -> str:
    s = riga["stato_compliance"]
    if s == "non_applicabile":
        return "valido"
    if s == "valido" and riga["scade_il"] and riga["scade_il"] <= ora + timedelta(days=GIORNI_IN_SCADENZA):
        return "in_scadenza"
    return s


def _persone(db: Session, ufficio_id: Optional[str], user_id: Optional[str] = None) -> list:
    if user_id:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            raise HTTPException(404, "Persona non trovata")
        return [u]
    if ufficio_id:
        return [p for p in persone_ufficio_e_sottouffici(db, ufficio_id) if p.is_active]
    return db.query(User).filter(User.is_active == True, User.is_external == False).order_by(User.full_name).all()  # noqa: E712


def costruisci_matrice(db: Session, ufficio_id: Optional[str], solo_obbligatori: bool = True, etichette: Optional[list] = None) -> dict:
    ora = datetime.now(timezone.utc)
    persone = _persone(db, ufficio_id)
    ids = {str(p.id) for p in persone}

    # Corsi richiesti: quelli dei percorsi attivi assegnati alla persona.
    richiesti: dict[str, set] = {i: set() for i in ids}
    for uid, corso_id in (db.query(PercorsoAssegnazione.user_id, PercorsoStep.corso_id)
                          .join(PercorsoFormativo, PercorsoFormativo.id == PercorsoAssegnazione.percorso_id)
                          .join(PercorsoStep, PercorsoStep.percorso_id == PercorsoFormativo.id)
                          .filter(PercorsoFormativo.is_active == True).all()):  # noqa: E712
        if str(uid) in richiesti:
            richiesti[str(uid)].add(str(corso_id))

    # Stato migliore per (persona, corso) tra le iscrizioni.
    stati: dict[tuple, dict] = {}
    for r in _righe(db, ufficio_id, None, None):
        if r["user_id"] not in ids:
            continue
        stato = _stato_cella(r, ora)
        chiave = (r["user_id"], r["corso_id"])
        attuale = stati.get(chiave)
        if attuale is None or ORDINE_STATI.index(stato) < ORDINE_STATI.index(attuale["stato"]):
            stati[chiave] = {"stato": stato, "scade_il": r["scade_il"], "completato_il": r["data_completamento"]}

    corsi_ids = set().union(*richiesti.values()) if richiesti else set()
    if not solo_obbligatori:
        corsi_ids |= {c for (_, c) in stati}
    ammessi = corsi_con_etichette(db, etichette)
    if ammessi is not None:
        corsi_ids &= {str(c) for c in ammessi}
    corsi = {str(c.id): c.titolo for c in db.query(Corso).filter(Corso.id.in_(corsi_ids)).all()} if corsi_ids else {}
    colonne = sorted(corsi, key=lambda c: corsi[c].lower())

    uffici = {}
    for uid, nome in (db.query(UserGroup.user_id, Group.name).join(Group, Group.id == UserGroup.group_id)
                      .filter(Group.is_ufficio == True).all()):  # noqa: E712
        uffici.setdefault(str(uid), []).append(nome)

    righe, conteggi = [], {}
    for p in persone:
        pid = str(p.id)
        celle = {}
        for c in colonne:
            obbligatorio = c in richiesti[pid]
            cella = stati.get((pid, c))
            if cella is None:
                if not obbligatorio:
                    continue
                cella = {"stato": "mancante", "scade_il": None, "completato_il": None}
            celle[c] = {**cella, "obbligatorio": obbligatorio}
            if obbligatorio:
                conteggi[cella["stato"]] = conteggi.get(cella["stato"], 0) + 1
        if celle:
            righe.append({"user_id": pid, "persona": p.full_name, "email": p.email, "uffici": uffici.get(pid, []), "celle": celle})

    obbligatorie = sum(conteggi.values())
    conformi = conteggi.get("valido", 0) + conteggi.get("in_scadenza", 0)
    return {
        "generato_at": ora,
        "corsi": [{"id": c, "titolo": corsi[c]} for c in colonne],
        "persone": righe,
        "riepilogo": {"celle_obbligatorie": obbligatorie, "conformi": conformi,
                      "percentuale": round(conformi / obbligatorie * 100, 1) if obbligatorie else None, "per_stato": conteggi},
        "etichette": ETICHETTE,
    }


@router.get("/matrice")
def matrice(ufficio_id: Optional[str] = Query(None), solo_obbligatori: bool = Query(True), etichette: Optional[List[str]] = Query(None),
            db: Session = Depends(get_db), user=Depends(require_training_admin)):
    return costruisci_matrice(db, ufficio_id, solo_obbligatori, etichette)


def _tabella_matrice(m: dict):
    colonne = ["Persona", "Email", "Uffici"] + [c["titolo"] for c in m["corsi"]]
    righe = []
    for p in m["persone"]:
        riga = [p["persona"], p["email"], "; ".join(p["uffici"])]
        for c in m["corsi"]:
            cella = p["celle"].get(c["id"])
            if not cella:
                riga.append("")
                continue
            testo = ETICHETTE[cella["stato"]]
            if cella["scade_il"]:
                testo += f" (scade {cella['scade_il'].strftime('%d/%m/%Y')})"
            riga.append(testo)
        righe.append(riga)
    return colonne, righe


@router.get("/matrice/export")
def matrice_export(formato: str = Query("csv"), pagina: str = Query("A3"), ufficio_id: Optional[str] = Query(None),
                   solo_obbligatori: bool = Query(True), etichette: Optional[List[str]] = Query(None),
                   db: Session = Depends(get_db), user=Depends(require_training_admin)):
    colonne, righe = _tabella_matrice(costruisci_matrice(db, ufficio_id, solo_obbligatori, etichette))
    azienda = db.query(Azienda).first()
    return esporta(formato, "matrice_formativa", "Matrice formativa", colonne, righe, pagina, azienda.logo_path if azienda else None)


# --- Pacchetto per l'ispezione ---------------------------------------------------------

def _nome_file(testo: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", testo or "").strip("_")[:60] or "senza_nome"


@router.get("/pacchetto-ispezione")
def pacchetto_ispezione(request: Request, ufficio_id: Optional[str] = Query(None), user_id: Optional[str] = Query(None),
                        corso_id: Optional[str] = Query(None), da: Optional[datetime] = Query(None), a: Optional[datetime] = Query(None),
                        etichette: Optional[List[str]] = Query(None),
                        db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """ZIP con tutto cio' che serve a un ispettore per il perimetro scelto: registro,
    matrice, attestati emessi dalla piattaforma, attestati esterni caricati e un
    indice che collega ogni documento alla persona e al corso."""
    ora = datetime.now(timezone.utc)
    ids = {str(p.id) for p in _persone(db, ufficio_id, user_id)}
    ammessi = corsi_con_etichette(db, etichette)
    righe = [r for r in _righe(db, ufficio_id, da, a, corso_id, ammessi) if r["user_id"] in ids]

    docs = []  # (cartella, nome_file, percorso_su_disco, riga indice)
    for r in righe:
        if not r["data_completamento"]:
            continue
        persona = _nome_file(r["persona"])
        for c in db.query(Certificato).filter(Certificato.iscrizione_id == r["iscrizione_id"]).all():
            if c.pdf_path:
                docs.append((f"attestati/{persona}", f"{_nome_file(r['corso'])}_{c.codice_verifica}.pdf", c.pdf_path,
                             [r["persona"], r["email"], r["corso"], "attestato emesso dalla piattaforma", c.codice_verifica, r["data_completamento"]]))
        for n, ev in enumerate(db.query(Evidenza).filter(Evidenza.iscrizione_id == r["iscrizione_id"],
                                                          Evidenza.file_allegato_path.isnot(None)).all(), start=1):
            ext = (ev.file_allegato_path.rsplit(".", 1)[-1] if "." in ev.file_allegato_path else "bin")[:5]
            docs.append((f"attestati_esterni/{persona}", f"{_nome_file(r['corso'])}_{n}.{ext}", ev.file_allegato_path,
                         [r["persona"], r["email"], r["corso"], "attestato esterno caricato dall'Ufficio Formazione", "", r["data_completamento"]]))
    if len(docs) > MAX_FILE_PACCHETTO:
        raise HTTPException(400, f"Il perimetro contiene {len(docs)} documenti (massimo {MAX_FILE_PACCHETTO}): restringilo per ufficio, persona, corso o periodo.")

    docs = [d for d in docs if os.path.exists(d[2])]
    azienda = db.query(Azienda).first()
    logo = azienda.logo_path if azienda else None
    colonne_reg = ["Persona", "Email", "Uffici", "Corso", "Etichette", "Data edizione", "Stato iscrizione", "Data completamento", "Scade il", "Stato compliance", "Aggiornamento disponibile"]
    dati_reg = [[r["persona"], r["email"], "; ".join(r["uffici"]), r["corso"], "; ".join(r["etichette"]), r["data_edizione"], r["stato_iscrizione"],
                 r["data_completamento"], r["scade_il"], r["stato_compliance"], r["aggiornamento_disponibile"]] for r in righe]
    col_m, dati_m = _tabella_matrice(costruisci_matrice(db, ufficio_id, solo_obbligatori=False, etichette=etichette)) if not user_id else (None, None)

    perimetro = []
    if user_id:
        u = db.query(User).filter(User.id == user_id).first()
        perimetro.append(f"persona: {u.full_name} ({u.email})")
    if ufficio_id:
        g = db.query(Group).filter(Group.id == ufficio_id).first()
        perimetro.append(f"ufficio: {g.name if g else ufficio_id} (con i sotto-uffici)")
    if corso_id:
        c = db.query(Corso).filter(Corso.id == corso_id).first()
        perimetro.append(f"corso: {c.titolo if c else corso_id}")
    if etichette:
        perimetro.append(descrivi_filtro(db, etichette))
    if da or a:
        perimetro.append(f"completamenti dal {da.strftime('%d/%m/%Y') if da else 'inizio'} al {a.strftime('%d/%m/%Y') if a else 'oggi'}")
    base_url = (azienda.url_pubblico if azienda and azienda.url_pubblico else "").rstrip("/")
    leggimi = (
        f"PACCHETTO PER L'ISPEZIONE\n{azienda.ragione_sociale if azienda and azienda.ragione_sociale else ''}\n\n"
        f"Generato il {ora.astimezone().strftime('%d/%m/%Y alle %H:%M')} da {user.full_name}\n"
        f"Perimetro: {'; '.join(perimetro) if perimetro else 'tutta l’azienda'}\n\n"
        f"Contenuto\n- registro_formazione.xlsx / .pdf: una riga per persona e corso con stato, data di completamento e scadenza ({len(dati_reg)} righe)\n"
        + ("- matrice_formativa.xlsx: persone x corsi con lo stato di ciascuna cella\n" if col_m else "")
        + f"- attestati/: attestati emessi dalla piattaforma ({sum(1 for d in docs if d[0].startswith('attestati/'))})\n"
        f"- attestati_esterni/: attestati di corsi esterni caricati dall'Ufficio Formazione ({sum(1 for d in docs if d[0].startswith('attestati_esterni/'))})\n"
        "- indice_documenti.csv: collega ogni documento a persona, corso e codice di verifica\n\n"
        "Verifica di autenticità\nOgni attestato emesso dalla piattaforma riporta un codice di verifica. "
        + (f"Si controlla su {base_url}/api/certificati/verifica/<codice>.\n" if base_url else "Si controlla con il servizio pubblico di verifica della piattaforma.\n")
        + "\nStati: valido, in scadenza, scaduto, da aggiornare (il corso è stato aggiornato e va ripetuto), non completato, in corso, mancante (corso richiesto da un percorso ma mai iniziato).\n"
    )
    indice = io.StringIO()
    w = csv.writer(indice)
    w.writerow(["Persona", "Email", "Corso", "Tipo documento", "Codice di verifica", "Data completamento", "File nel pacchetto"])
    for cartella, nome, _, riga in docs:
        w.writerow([neutralizza(riga[0]), neutralizza(riga[1]), neutralizza(riga[2]), riga[3], riga[4], riga[5].strftime("%d/%m/%Y") if riga[5] else "", f"{cartella}/{nome}"])

    radice = f"pacchetto-ispezione-{ora.strftime('%Y%m%d')}"
    tmp = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{radice}/LEGGIMI.txt", leggimi)
        z.writestr(f"{radice}/registro_formazione.xlsx", _a_excel("Registro formazione", colonne_reg, dati_reg))
        if len(dati_reg) <= MAX_RIGHE_PDF:
            z.writestr(f"{radice}/registro_formazione.pdf", _a_pdf("Registro formazione", colonne_reg, dati_reg, "A3", logo))
        if col_m:
            z.writestr(f"{radice}/matrice_formativa.xlsx", _a_excel("Matrice formativa", col_m, dati_m))
        z.writestr(f"{radice}/indice_documenti.csv", "﻿" + indice.getvalue())
        usati = set()
        for cartella, nome, percorso, _ in docs:
            destinazione = f"{radice}/{cartella}/{nome}"
            if destinazione in usati:
                continue
            usati.add(destinazione)
            z.write(percorso, destinazione)
    tmp.seek(0)
    audit_svc.log_from_request(db, request, user, "PACCHETTO_ISPEZIONE", entity_type="registro", entity_name="Pacchetto per l'ispezione",
                                detail=f"{'; '.join(perimetro) or 'tutta l’azienda'} - {len(dati_reg)} righe, {len(docs)} documenti")
    db.commit()

    def flusso():
        try:
            while True:
                blocco = tmp.read(1024 * 1024)
                if not blocco:
                    break
                yield blocco
        finally:
            tmp.close()
    return StreamingResponse(flusso(), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{radice}.zip"'})
