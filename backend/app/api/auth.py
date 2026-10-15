from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import csv, io
from ..database import get_db
from ..config import settings
from ..models.user import User, UserRole
from ..models.group import Group, UserGroup
from ..models.organizzazione import Organizzazione
from ..services.auth import verify_password, hash_password, token_per_utente
from ..services.password_policy import password_valida, genera_password_temporanea, REQUISITI_PASSWORD
from ..services import rate_limit
from ..models.notification import Notification
from ..services import audit as audit_svc
from ..services.percorsi_sync import sincronizza_assegnazioni
from ..services.gerarchia import responsabili_di, sottoposti_di, e_responsabile, uffici_guidati_da
from ..services.email import invia_email, dopo_il_commit
from ..services.inviti import crea_link_invito, invia_invito
from ..services.offboarding import disattiva_utente, invita_promossi
from .deps import get_current_user, require_training_admin, require_admin_tecnico

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr; password: str

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = None  # vuota: la sceglie la persona (link via email) o viene generata una temporanea
    role: UserRole = UserRole.user
    is_external: bool = False
    organizzazione_id: Optional[str] = None
    group_ids: List[str] = []
    data_ingresso: Optional[datetime] = None
    origine_credenziali: str = "locale"

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_external: Optional[bool] = None
    organizzazione_id: Optional[str] = None
    group_ids: Optional[List[str]] = None
    can_see_all: Optional[bool] = None
    data_ingresso: Optional[datetime] = None
    origine_credenziali: Optional[str] = None

def _is_docente_di_qualcosa(user_id, db: Session) -> bool:
    from ..models.edizione import EdizioneDocente
    return db.query(EdizioneDocente).filter(EdizioneDocente.user_id == user_id).first() is not None

def _serialize_user(u: User, db: Session):
    memberships = db.query(UserGroup).options(joinedload(UserGroup.group)).filter(UserGroup.user_id == u.id).all()
    groups = [{"id": str(m.group_id), "name": m.group.name, "color": m.group.color} for m in memberships if m.group]
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name,
        "role": u.role, "is_active": u.is_active,
        "is_external": u.is_external,
        "organizzazione_id": str(u.organizzazione_id) if u.organizzazione_id else None,
        "can_see_all": u.can_see_all or False,
        "data_ingresso": u.data_ingresso,
        "origine_credenziali": u.origine_credenziali,
        "password_da_cambiare": bool(u.password_da_cambiare and u.origine_credenziali == "locale"),
        "is_docente": _is_docente_di_qualcosa(u.id, db),
        "groups": groups, "created_at": u.created_at,
    }

def _assign_groups(user_id: str, group_ids: List[str], db: Session):
    db.query(UserGroup).filter(UserGroup.user_id == user_id).delete()
    for gid in group_ids:
        db.add(UserGroup(user_id=user_id, group_id=gid))
    db.flush()

MAX_TENTATIVI = 5
BLOCCO_MINUTI = 15
LOGIN_PER_IP = 30  # ogni 15 minuti: protegge da tentativi distribuiti su molte email

def _password_non_valida():
    return HTTPException(400, f"Password non valida: richiesti {REQUISITI_PASSWORD}")

# Stessa risposta per password sbagliata, email inesistente e account sospeso: chi prova non puo'
# capire se un indirizzo e' registrato ne' se un account e' bloccato (e il proprietario non viene
# "confermato" a un attaccante). Il blocco dura poco, si toglie con "Password dimenticata" ed e' segnalato
# agli Admin tecnici e nell'audit.
MESSAGGIO_ACCESSO = "Credenziali non valide, oppure accesso sospeso per troppi tentativi: riprova tra qualche minuto o usa «Password dimenticata»."
_HASH_FITTIZIO = hash_password("password-fittizia-per-pareggiare-i-tempi")

@router.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    chiave_ip = f"login:{audit_svc.ip_client(request)}"
    # Il limite per indirizzo conta solo i tentativi falliti: dietro un proxy che nasconde l'IP vero
    # tutti condividono lo stesso indirizzo, e i login riusciti non devono consumarlo.
    if rate_limit.superato(chiave_ip, LOGIN_PER_IP, 15 * 60):
        raise HTTPException(429, "Troppi tentativi di accesso da questo indirizzo. Riprova tra qualche minuto.")
    user = db.query(User).filter(func.lower(User.email) == data.email.lower()).first()
    now = datetime.now(timezone.utc)
    sospeso = bool(user and user.bloccato_fino and user.bloccato_fino > now)
    # il controllo della password si fa sempre (anche per email inesistenti o account sospesi): tempi uguali
    password_ok = verify_password(data.password, user.hashed_password if user else _HASH_FITTIZIO)
    if sospeso or not user or not password_ok:
        rate_limit.registra(chiave_ip, 15 * 60)
        audit_svc.log_from_request(db, request, None, "LOGIN_FAILED", detail=f"{'Account sospeso' if sospeso else 'Tentativo fallito'}: {data.email}")
        if user and not sospeso:
            user.tentativi_falliti = (user.tentativi_falliti or 0) + 1
            if user.tentativi_falliti >= MAX_TENTATIVI:
                user.tentativi_falliti = 0
                user.bloccato_fino = now + timedelta(minutes=BLOCCO_MINUTI)
                audit_svc.log_from_request(db, request, user, "ACCOUNT_BLOCCATO", entity_type="user", entity_id=str(user.id),
                                            entity_name=user.email, detail=f"{BLOCCO_MINUTI} minuti dopo {MAX_TENTATIVI} tentativi falliti")
                chiave = f"account_bloccato:{user.id}:{now:%Y%m%d%H}"
                if not db.query(Notification).filter(Notification.dedup_key == chiave).first():
                    # solo in-app: niente invio email dentro la richiesta di login (rallenterebbe chi accede)
                    for adm in db.query(User).filter(User.role == UserRole.admin_tecnico, User.is_active == True).all():  # noqa: E712
                        db.add(Notification(user_id=adm.id, tipo="account_bloccato", dedup_key=chiave, link="/audit-log",
                                            testo=f"L'account {user.email} è stato sospeso per {BLOCCO_MINUTI} minuti dopo {MAX_TENTATIVI} tentativi di accesso falliti."))
        db.commit()
        raise HTTPException(401, MESSAGGIO_ACCESSO)
    if not user.is_active:
        raise HTTPException(401, "Utente disabilitato")
    # Con l'SSO attivo chi ha le credenziali gestite dal dominio entra solo da li';
    # l'Admin tecnico resta sempre ammesso con password (accesso di emergenza se l'IdP e' giu').
    if settings.sso_enabled and user.origine_credenziali != "locale" and user.role != UserRole.admin_tecnico:
        audit_svc.log_from_request(db, request, user, "LOGIN_FAILED", detail="password non ammessa: credenziali gestite dal dominio")
        db.commit()
        raise HTTPException(401, "Questo account usa l'accesso aziendale: usa il pulsante «Accedi con l'account aziendale»")
    user.tentativi_falliti = 0
    user.bloccato_fino = None
    token = token_per_utente(user)
    audit_svc.log_from_request(db, request, user, "LOGIN", entity_type="user", entity_id=str(user.id), entity_name=user.email)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, db)}

@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize_user(user, db)

@router.put("/me/password")
def cambia_password(data: PasswordChange, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.origine_credenziali != "locale":
        raise HTTPException(400, "Le credenziali sono gestite centralmente: non puoi cambiare la password da qui")
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Password attuale non corretta")
    if not password_valida(data.new_password):
        raise _password_non_valida()
    if data.new_password == data.current_password:
        raise HTTPException(400, "La nuova password deve essere diversa da quella attuale")
    user.hashed_password = hash_password(data.new_password)
    user.password_da_cambiare = False
    user.token_version = (user.token_version or 0) + 1  # chiude le altre sessioni
    audit_svc.log_from_request(db, request, user, "PASSWORD_CAMBIATA", entity_type="user", entity_id=str(user.id), entity_name=user.email)
    db.commit()
    # Nuovo token solo per la sessione che ha fatto il cambio: le altre restano invalidate.
    return {"ok": True, "access_token": token_per_utente(user)}

@router.get("/users")
def list_users(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    users = db.query(User).order_by(User.full_name).all()
    return [_serialize_user(u, db) for u in users]

@router.get("/users/simple")
def list_users_simple(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista semplificata utenti attivi - usata per i picker (es. scelta docenti)."""
    users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
    return [{"id": str(u.id), "full_name": u.full_name, "email": u.email, "is_external": u.is_external} for u in users]

@router.post("/users")
def create_user(data: UserCreate, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    if db.query(User).filter(func.lower(User.email) == data.email.lower()).first():
        raise HTTPException(400, "Email già esistente")
    if data.is_external and not data.organizzazione_id:
        raise HTTPException(400, "Un utente esterno deve avere un'organizzazione di riferimento")
    if data.password and not password_valida(data.password):
        raise _password_non_valida()
    scelta_dall_admin = bool(data.password)
    password = data.password or genera_password_temporanea()
    u = User(
        email=data.email, full_name=data.full_name,
        hashed_password=hash_password(password),
        role=data.role, is_external=data.is_external,
        organizzazione_id=data.organizzazione_id,
        data_ingresso=data.data_ingresso,
        origine_credenziali=data.origine_credenziali,
        password_da_cambiare=True,  # password scelta da altri: la persona ne sceglie una sua
    )
    db.add(u); db.flush()
    if data.group_ids:
        _assign_groups(str(u.id), data.group_ids, db)
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="user", entity_id=str(u.id), entity_name=u.email)
    sincronizza_assegnazioni(db)
    link = crea_link_invito(db, u) if u.origine_credenziali == "locale" else None
    db.commit(); db.refresh(u)
    invitato = bool(link) and invia_invito(u.email, u.full_name, link)
    # Una password che l'admin non ha scelto e che non e' partita per email gli va mostrata (una volta sola).
    mostra = password if (u.origine_credenziali == "locale" and not scelta_dall_admin and not invitato) else None
    return {**_serialize_user(u, db), "invito_inviato": invitato, "password_temporanea": mostra}

@router.post("/users/import-csv")
async def import_users_csv(file: UploadFile = File(...), modo: str = Query("nuovi"), request: Request = None,
                            db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    """Import bulk per onboarding: CSV con colonne (case-insensitive) email,
    full_name, password (opz.), role (opz., default 'user'), is_external
    (opz.), organizzazione (ragione sociale, opz.), gruppi (nomi separati da
    ';' o '|', opz.), data_ingresso (opz., YYYY-MM-DD). Righe con errori vengono
    segnalate ma non bloccano le altre. Se SMTP è configurato le credenziali
    vengono inviate per email, altrimenti tornano nella risposta.

    Con modo=cessati il file e' invece un elenco di disattivazione massiva: basta
    la colonna email, ogni riga disattiva l'utente corrispondente (lo storico
    formativo resta intatto). E' una scelta esplicita, mai dedotta dal nome del
    file; gli Admin tecnici non si disattivano da qui."""
    if modo not in ("nuovi", "cessati"):
        raise HTTPException(400, "Modo non valido: usa nuovi o cessati")
    if modo == "nuovi" and "cessat" in (file.filename or "").lower():
        raise HTTPException(400, "Il nome del file suggerisce un elenco di cessati, ma hai scelto di creare nuovi utenti: scegli «Disattiva cessati» se è quello che vuoi.")
    if modo == "cessati":
        return await _disattiva_utenti_csv(file, request, db, user)

    raw = (await file.read()).decode("utf-8-sig")
    righe_testo = raw.splitlines()
    if not righe_testo:
        raise HTTPException(400, "File vuoto")
    delimitatore = ";" if righe_testo[0].count(";") > righe_testo[0].count(",") else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimitatore)
    reader.fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    if "email" not in reader.fieldnames or not ("full_name" in reader.fieldnames or "nome" in reader.fieldnames):
        raise HTTPException(400, "Intestazioni richieste: email, full_name (o nome)")

    gruppi_tutti = {g.name.lower(): g for g in db.query(Group).all()}
    org_tutte = {o.ragione_sociale.lower(): o for o in db.query(Organizzazione).all()}

    righe = []
    creati = 0
    for n, row in enumerate(reader, start=2):  # riga 1 = intestazione
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = row.get("email")
        full_name = row.get("full_name") or row.get("nome")
        if not email or not full_name:
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "email o nome mancante"})
            continue
        if db.query(User).filter(func.lower(User.email) == email.lower()).first():
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "email già esistente"})
            continue
        is_external = row.get("is_external", "").lower() in ("true", "si", "sì", "1", "yes", "x")
        org = None
        if row.get("organizzazione"):
            org = org_tutte.get(row["organizzazione"].lower())
            if not org:
                righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": f"organizzazione \"{row['organizzazione']}\" non trovata"})
                continue
        if is_external and not org:
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "utente esterno senza organizzazione"})
            continue
        role_raw = row.get("role") or "user"
        try:
            role = UserRole(role_raw)
        except ValueError:
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": f"ruolo \"{role_raw}\" non valido"})
            continue
        data_ingresso = None
        if row.get("data_ingresso"):
            try:
                data_ingresso = datetime.strptime(row["data_ingresso"], "%Y-%m-%d")
            except ValueError:
                righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "data_ingresso non valida (formato YYYY-MM-DD)"})
                continue
        password = row.get("password") or genera_password_temporanea()
        if not password_valida(password):
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": f"password non valida: richiesti {REQUISITI_PASSWORD}"})
            continue

        u = User(
            email=email, full_name=full_name,
            hashed_password=hash_password(password),
            role=role, is_external=is_external,
            organizzazione_id=org.id if org else None,
            data_ingresso=data_ingresso,
            origine_credenziali="locale",
            password_da_cambiare=True,
        )
        db.add(u); db.flush()

        gruppi_non_trovati = []
        if row.get("gruppi"):
            group_ids = []
            for nome in row["gruppi"].replace("|", ";").split(";"):
                nome = nome.strip()
                if not nome:
                    continue
                g = gruppi_tutti.get(nome.lower())
                if g:
                    group_ids.append(str(g.id))
                else:
                    gruppi_non_trovati.append(nome)
            if group_ids:
                _assign_groups(str(u.id), group_ids, db)

        link = crea_link_invito(db, u)
        db.flush()
        inviata = bool(link)
        if link:
            dopo_il_commit(db, invia_invito, email, full_name, link)  # il link, mai la password; parte solo a commit riuscito
        creati += 1
        messaggio = "creato"
        if gruppi_non_trovati:
            messaggio += f" (gruppi non trovati: {', '.join(gruppi_non_trovati)})"
        righe.append({
            "riga": n, "email": email, "esito": "creato", "messaggio": messaggio,
            "email_inviata": inviata, "password": None if inviata else password,
        })

    if request is not None:
        audit_svc.log_from_request(db, request, user, "CREATE", entity_type="user", entity_name=f"import CSV: {creati} utenti creati")
    sincronizza_assegnazioni(db)
    db.commit()
    return {"totale": len(righe), "creati": creati, "errori": len(righe) - creati, "righe": righe}

async def _disattiva_utenti_csv(file: UploadFile, request: Request, db: Session, user) -> dict:
    raw = (await file.read()).decode("utf-8-sig")
    righe_testo = raw.splitlines()
    if not righe_testo:
        raise HTTPException(400, "File vuoto")
    delimitatore = ";" if righe_testo[0].count(";") > righe_testo[0].count(",") else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimitatore)
    reader.fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    if "email" not in reader.fieldnames:
        raise HTTPException(400, "Intestazione richiesta: email")

    righe = []
    disattivati = 0
    promossi_tutti = []
    for n, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip()
        if not email:
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "email mancante"})
            continue
        u = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not u:
            righe.append({"riga": n, "email": email, "esito": "ignorato", "messaggio": "email non trovata"})
            continue
        if not u.is_active:
            righe.append({"riga": n, "email": email, "esito": "ignorato", "messaggio": "già disattivato"})
            continue
        if u.role == UserRole.admin_tecnico:
            righe.append({"riga": n, "email": email, "esito": "errore", "messaggio": "Admin tecnico: non si disattiva da un elenco"})
            continue
        r = disattiva_utente(db, u)
        promossi_tutti.extend(r["promossi"])
        disattivati += 1
        messaggio = "disattivato"
        if r["posti_liberati"]:
            messaggio += f" ({r['posti_liberati']} iscrizioni aperte annullate)"
        if r["avvisi"]:
            messaggio += " - attenzione: " + "; ".join(r["avvisi"])
        righe.append({"riga": n, "email": email, "esito": "disattivato", "messaggio": messaggio})

    if request is not None:
        audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="user", entity_name=f"import CSV cessati: {disattivati} utenti disattivati")
    db.commit()
    invita_promossi(db, promossi_tutti)
    return {"totale": len(righe), "creati": 0, "errori": sum(1 for r in righe if r["esito"] == "errore"), "righe": righe}

def _solo_se_stesso_o_formazione(user: User, user_id: str):
    """La struttura dei responsabili non e' un elenco pubblico: la vede la persona per se' e la Formazione."""
    if str(user.id) != str(user_id) and user.role not in (UserRole.admin_tecnico, UserRole.training_admin):
        raise HTTPException(403, "Non puoi consultare la struttura di un'altra persona")

@router.get("/users/{user_id}/responsabili")
def get_responsabili(user_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _solo_se_stesso_o_formazione(user, user_id)
    """Responsabile(i) della persona, derivati dagli uffici a cui appartiene
    (può averne più di uno se è su più uffici in parallelo, es. part-time)."""
    responsabili = responsabili_di(db, user_id)
    return [{"id": str(r.id), "full_name": r.full_name, "email": r.email} for r in responsabili]

@router.get("/users/{user_id}/uffici-guidati")
def get_uffici_guidati(user_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _solo_se_stesso_o_formazione(user, user_id)
    """È responsabile di almeno un ufficio? (guida la UI: voci riservate ai
    responsabili come richiesta corso/fabbisogno formativo)."""
    uffici = uffici_guidati_da(db, user_id)
    return [{"id": str(u.id), "name": u.name} for u in uffici]

@router.get("/users/{user_id}/sottoposti")
def get_sottoposti(user_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _solo_se_stesso_o_formazione(user, user_id)
    """Tutte le persone sotto gli uffici guidati da questo utente (diretti e
    nei sotto-uffici, risalendo/scendendo l'albero)."""
    sottoposti = sottoposti_di(db, user_id)
    return [{"id": str(s.id), "full_name": s.full_name, "email": s.email} for s in sottoposti]

@router.put("/users/{user_id}")
def update_user(user_id: str, data: UserUpdate, request: Request,
                 db: Session = Depends(get_db), current=Depends(require_admin_tecnico)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    if data.full_name is not None: u.full_name = data.full_name
    avvisi_disattivazione, promossi = [], []
    if data.is_active is not None and data.is_active != u.is_active:
        if data.is_active is False:
            if str(u.id) == str(current.id):
                raise HTTPException(400, "Non puoi disattivare il tuo stesso account")
            if u.role == UserRole.admin_tecnico and db.query(User).filter(User.role == UserRole.admin_tecnico, User.is_active == True, User.id != u.id).count() == 0:  # noqa: E712
                raise HTTPException(400, "È l'ultimo Admin tecnico attivo: non si può disattivare")
            esito_disattivazione = disattiva_utente(db, u)  # chiude iscrizioni aperte, dispositivi, calendario e sessioni
            avvisi_disattivazione, promossi = esito_disattivazione["avvisi"], esito_disattivazione["promossi"]
        else:
            u.is_active = True
    password_cambiata = False
    if data.password:
        if not password_valida(data.password):
            raise _password_non_valida()
        u.hashed_password = hash_password(data.password)
        u.password_da_cambiare = True
        u.token_version = (u.token_version or 0) + 1
        u.tentativi_falliti = 0
        u.bloccato_fino = None
        password_cambiata = True
    if data.role is not None and data.role != u.role:
        if u.role == UserRole.admin_tecnico:
            if str(u.id) == str(current.id):
                raise HTTPException(400, "Non puoi cambiare il tuo stesso ruolo")
            if u.is_active and db.query(User).filter(User.role == UserRole.admin_tecnico, User.is_active == True, User.id != u.id).count() == 0:  # noqa: E712
                raise HTTPException(400, "È l'ultimo Admin tecnico attivo: non si può cambiare il suo ruolo")
        u.role = data.role
    if data.is_external is not None: u.is_external = data.is_external
    if data.organizzazione_id is not None: u.organizzazione_id = data.organizzazione_id or None
    if u.is_external and not u.organizzazione_id:
        raise HTTPException(400, "Un utente esterno deve avere un'organizzazione di riferimento")
    if data.group_ids is not None: _assign_groups(user_id, data.group_ids, db)
    if data.can_see_all is not None: u.can_see_all = data.can_see_all
    if data.data_ingresso is not None: u.data_ingresso = data.data_ingresso
    if data.origine_credenziali is not None: u.origine_credenziali = data.origine_credenziali
    audit_svc.log_from_request(db, request, current, "UPDATE", entity_type="user", entity_id=str(u.id), entity_name=u.email,
                                detail="password reimpostata dall'amministratore" if password_cambiata else None)
    sincronizza_assegnazioni(db)
    db.commit()
    invita_promossi(db, promossi)
    return {**_serialize_user(u, db), "avvisi_disattivazione": avvisi_disattivazione}
