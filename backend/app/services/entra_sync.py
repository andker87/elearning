"""Sincronizzazione utenti da Microsoft Entra ID.

Il gruppo Entra indicato in ENTRA_SYNC_GRUPPO_ID definisce chi fa parte della
piattaforma. Il piano (anteprima) confronta quel gruppo con gli utenti interni
della piattaforma e propone: creare chi manca, aggiornare i nomi, disattivare chi
e' uscito (fuori dal gruppo o account disabilitato) e riattivare chi e' tornato.
Gli utenti esterni e gli Admin tecnici non vengono mai toccati automaticamente."""
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.notification import Notification
from ..models.user import User
from . import audit as audit_svc
from .auth import hash_password
from .offboarding import avvisi_disattivazione, disattiva_utente, invita_promossi
from .password_policy import genera_password_temporanea
from .persone import dividi_nome
from .percorsi_sync import sincronizza_assegnazioni
from .impronte import impronta

GRAPH = "https://graph.microsoft.com/v1.0"
GIORNI_ASSUNZIONE_RECENTE = 60  # solo i nuovi assunti fanno scattare i percorsi "ingresso in azienda"
SOGLIA_DISATTIVAZIONI_PCT = 20
SOGLIA_DISATTIVAZIONI_MIN = 5
SOGLIA_CREAZIONI = 200


class EntraErrore(Exception):
    pass


def _token() -> str:
    r = httpx.post(f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token", timeout=15, data={
        "client_id": settings.GRAPH_CLIENT_ID, "client_secret": settings.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
    if r.status_code != 200:
        raise EntraErrore(f"autenticazione Graph rifiutata ({r.status_code})")
    return r.json()["access_token"]


def leggi_membri() -> list:
    """Membri (anche indiretti) del gruppo Entra, con stato dell'account."""
    if not settings.entra_sync_enabled:
        raise EntraErrore("sincronizzazione non configurata")
    intestazioni = {"Authorization": f"Bearer {_token()}"}
    url = (f"{GRAPH}/groups/{settings.ENTRA_SYNC_GRUPPO_ID}/transitiveMembers/microsoft.graph.user"
           "?$select=id,displayName,givenName,surname,mail,userPrincipalName,proxyAddresses,accountEnabled,employeeHireDate&$top=999")
    membri = []
    while url:
        r = httpx.get(url, headers=intestazioni, timeout=30)
        if r.status_code != 200:
            raise EntraErrore(f"Graph ha risposto {r.status_code} leggendo il gruppo")
        dati = r.json()
        for m in dati.get("value", []):
            email = (m.get("mail") or m.get("userPrincipalName") or "").strip().lower()
            if "@" not in email:
                continue
            assunto = None
            if m.get("employeeHireDate"):
                try:
                    assunto = datetime.fromisoformat(m["employeeHireDate"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            # tutti gli indirizzi con cui la persona puo' essere registrata qui (mail, UPN, alias SMTP)
            indirizzi = {email, (m.get("userPrincipalName") or "").strip().lower(), (m.get("mail") or "").strip().lower()}
            indirizzi |= {a[5:].strip().lower() for a in (m.get("proxyAddresses") or []) if isinstance(a, str) and a.lower().startswith("smtp:")}
            membri.append({"email": email, "indirizzi": sorted(i for i in indirizzi if "@" in i), "nome": (m.get("displayName") or "").strip(),
                           "given": (m.get("givenName") or "").strip(), "cognome": (m.get("surname") or "").strip(),
                           "attivo": m.get("accountEnabled") is not False, "assunto_il": assunto})
        url = dati.get("@odata.nextLink")
    return membri


def _nome_membro(m: dict) -> tuple:
    """(nome, cognome) di un membro: givenName e surname di Entra se ci sono entrambi, altrimenti il nome visualizzato diviso."""
    if m.get("given") and m.get("cognome"):
        return m["given"][:100], m["cognome"][:100]
    return dividi_nome((m.get("nome") or m["email"].split("@")[0])[:200])


def calcola_piano(db: Session, membri: list) -> dict:
    ora = datetime.now(timezone.utc)
    per_indirizzo = {}
    for m in membri:
        for ind in (m.get("indirizzi") or [m["email"]]):
            per_indirizzo.setdefault(ind, m)
    domini = sorted({i.split("@")[1] for m in membri for i in (m.get("indirizzi") or [m["email"]])})
    piattaforma = {u.email.lower(): u for u in db.query(User).all()}
    piano = {"generato_at": ora, "membri_entra": len(membri), "domini": domini,
             "crea": [], "aggiorna": [], "disattiva": [], "riattiva": [], "esclusi": [], "freno": None}

    for m in membri:
        u = next((piattaforma[i] for i in (m.get("indirizzi") or [m["email"]]) if i in piattaforma), None)
        if m["attivo"]:
            if not u:
                recente = m["assunto_il"] and ora - m["assunto_il"] <= timedelta(days=GIORNI_ASSUNZIONE_RECENTE)
                nome_n, cognome_n = _nome_membro(m)
                piano["crea"].append({"email": m["email"], "nome": f"{nome_n} {cognome_n}".strip(), "nome_n": nome_n, "cognome_n": cognome_n,
                                      "data_ingresso": m["assunto_il"] if recente else None})
            elif u.is_external:
                continue
            elif not u.is_active:
                piano["riattiva"].append({"email": u.email, "nome": u.full_name})
            elif (m["nome"] or (m.get("given") and m.get("cognome"))) and _nome_membro(m) != (u.nome, u.cognome):
                nome_n, cognome_n = _nome_membro(m)
                piano["aggiorna"].append({"email": u.email, "da": u.full_name, "a": f"{nome_n} {cognome_n}".strip(), "nome_n": nome_n, "cognome_n": cognome_n})

    # Uscite: account disabilitato in Entra, oppure non piu' nel gruppo (solo per i domini del gruppo).
    candidati = [u for u in piattaforma.values() if u.is_active and not u.is_external and u.email.lower().split("@")[-1] in domini]
    in_ambito = len(candidati)
    for u in candidati:
        m = per_indirizzo.get(u.email.lower())
        motivo = "account disabilitato in Entra" if (m and not m["attivo"]) else ("non più nel gruppo Entra" if not m else None)
        if not motivo:
            continue
        if u.is_admin:
            piano["esclusi"].append({"email": u.email, "nome": u.full_name, "motivo": f"Admin tecnico ({motivo}): non si disattiva in automatico"})
            continue
        piano["disattiva"].append({"email": u.email, "nome": u.full_name, "motivo": motivo, "avvisi": avvisi_disattivazione(db, u)})

    # Mai oltre la meta' degli utenti in ambito: su installazioni piccole un gruppo sbagliato non li disattiva tutti.
    limite = min(max(SOGLIA_DISATTIVAZIONI_MIN, in_ambito * SOGLIA_DISATTIVAZIONI_PCT // 100), max(2, in_ambito // 2))
    if len(piano["disattiva"]) > limite or (in_ambito and len(piano["disattiva"]) >= in_ambito):
        piano["freno"] = (f"{len(piano['disattiva'])} disattivazioni su {in_ambito} utenti in ambito (limite {limite}): "
                          "controlla che il gruppo Entra sia quello giusto")
    elif len(piano["crea"]) > SOGLIA_CREAZIONI:
        piano["freno"] = f"{len(piano['crea'])} nuovi utenti in un solo giro (limite {SOGLIA_CREAZIONI})"
    return piano


def impronta_piano(piano: dict) -> str:
    """Identifica le persone coinvolte: chi applica deve applicare quello che ha visto in anteprima."""
    import hashlib, json
    # oltre a chi e all'azione, i valori che verranno scritti (nome, data di ingresso): se cambiano in Entra dopo l'anteprima, l'impronta cambia
    voci = sorted(json.dumps([k, x], sort_keys=True, default=str) for k in ("crea", "aggiorna", "disattiva", "riattiva")
                  for x in ({c: v for c, v in y.items() if c != "avvisi"} for y in piano[k]))
    return hashlib.sha256("\n".join(voci).encode()).hexdigest()[:16]


def applica_piano(db: Session, piano: dict, request=None, admin=None, riattiva: bool = False) -> dict:
    esito = {"creati": 0, "aggiornati": 0, "disattivati": 0, "riattivati": 0, "posti_liberati": 0, "avvisi": []}
    promossi = []

    def traccia(azione, email, dettaglio):
        audit_svc.log_from_request(db, request, admin, azione, entity_type="user", entity_name=email, detail=f"sincronizzazione Entra - {dettaglio}")

    for c in piano["crea"]:
        if db.query(User).filter(User.email_idx == impronta(c["email"])).first():
            continue
        try:
            with db.begin_nested():
                db.add(User(email=c["email"], nome=c["nome_n"], cognome=c["cognome_n"], is_external=False,
                            hashed_password=hash_password(genera_password_temporanea() + secrets.token_urlsafe(8)),
                            origine_credenziali="dominio", data_ingresso=c["data_ingresso"]))
                db.flush()
        except IntegrityError:
            if not db.query(User).filter(User.email_idx == impronta(c["email"])).first():
                raise
            continue   # creato nel frattempo da un altro percorso: non si conta ne' si registra
        traccia("CREATE", c["email"], "nuovo nel gruppo")
        esito["creati"] += 1
    db.flush()
    for a in piano["aggiorna"]:
        u = db.query(User).filter(User.email_idx == impronta(a["email"])).first()
        if u and (u.nome, u.cognome) != (a["nome_n"], a["cognome_n"]):
            u.nome, u.cognome = a["nome_n"], a["cognome_n"]
            traccia("UPDATE", u.email, f"nome: {a['da']} → {a['a']}")
            esito["aggiornati"] += 1
    for d in piano["disattiva"]:
        u = db.query(User).filter(User.email_idx == impronta(d["email"])).first()
        if not u or not u.is_active or u.is_admin:
            continue
        r = disattiva_utente(db, u)
        traccia("DISATTIVA_UTENTE", u.email, d["motivo"] + (f" - posti liberati: {r['posti_liberati']}" if r["posti_liberati"] else ""))
        esito["disattivati"] += 1
        esito["posti_liberati"] += r["posti_liberati"]
        promossi += r["promossi"]
        esito["avvisi"] += [f"{u.full_name}: {a}" for a in r["avvisi"]]
    if riattiva:
        for r_ in piano["riattiva"]:
            u = db.query(User).filter(User.email_idx == impronta(r_["email"])).first()
            if u and not u.is_active:
                u.is_active = True
                traccia("UPDATE", u.email, "riattivato: di nuovo nel gruppo")
                esito["riattivati"] += 1
    sincronizza_assegnazioni(db)
    db.commit()
    invita_promossi(db, promossi)
    return esito


def _avvisa_responsabili(db: Session, testo: str):
    for u in db.query(User).filter(User.is_active == True, or_(User.is_admin == True, User.is_formazione == True)).all():  # noqa: E712
        db.add(Notification(user_id=u.id, tipo="sync_entra", testo=testo, link="/sincronizzazione-utenti"))


def riepilogo(esito: dict) -> str:
    return (f"creati {esito['creati']}, aggiornati {esito['aggiornati']}, disattivati {esito['disattivati']}"
            + (f", riattivati {esito['riattivati']}" if esito["riattivati"] else ""))


def sincronizza_automatico(db: Session) -> str:
    """Giro notturno (ENTRA_SYNC_AUTO). Non riattiva nessuno e si ferma davanti a
    un piano sospetto: in quel caso avvisa invece di agire."""
    piano = calcola_piano(db, leggi_membri())
    if piano["freno"]:
        _avvisa_responsabili(db, f"Sincronizzazione Entra sospesa: {piano['freno']}. Controlla e applica a mano.")
        db.commit()
        return f"sospesa: {piano['freno']}"
    esito = applica_piano(db, piano)
    if esito["avvisi"] or piano["riattiva"]:
        extra = "; ".join(esito["avvisi"][:5]) + (f" — {len(piano['riattiva'])} persone da riattivare" if piano["riattiva"] else "")
        _avvisa_responsabili(db, f"Sincronizzazione Entra: {riepilogo(esito)}. {extra}")
        db.commit()
    return riepilogo(esito)
