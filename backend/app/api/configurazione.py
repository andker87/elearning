import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.corso import Corso
from ..models.group import Group, UserGroup
from ..models.mansione import Mansione, UserMansione
from ..services.persone import permessi_testo
from ..models.organizzazione import Organizzazione
from ..models.percorso import PercorsoFormativo
from ..models.user import User
from ..services import audit as audit_svc
from ..services import configurazione as svc
from ..services.export import esporta
from .deps import require_admin_tecnico, require_training_admin

router = APIRouter(prefix="/api", tags=["configurazione"])


@router.get("/admin/configurazione/export")
def esporta_configurazione(request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    contenuto = svc.esporta(db)
    audit_svc.log_from_request(db, request, user, "CONFIG_EXPORT", entity_type="configurazione", entity_name="Esportazione configurazione",
                                detail=f"{len(contenuto['gruppi'])} gruppi, {len(contenuto['corsi'])} corsi, {len(contenuto['percorsi'])} percorsi, {len(contenuto['organizzazioni'])} società")
    db.commit()
    nome = f"configurazione-{datetime.now().strftime('%Y%m%d')}.json"
    return Response(json.dumps(contenuto, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


class ImportIn(BaseModel):
    contenuto: dict
    applica: bool = False


@router.post("/admin/configurazione/import")
def importa_configurazione(data: ImportIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    """Senza applica=true mostra solo l'anteprima: nulla viene scritto."""
    try:
        risultato = svc.importa(db, data.contenuto, data.applica)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(400, f"File incompleto: manca il campo {e}")
    if data.applica:
        t = risultato["totali"]
        audit_svc.log_from_request(db, request, user, "CONFIG_IMPORT", entity_type="configurazione", entity_name="Importazione configurazione",
                                    detail=f"creati {t['creati']}, aggiornati {t['aggiornati']}; file della versione {data.contenuto.get('versione_app', '?')}")
        db.commit()
    return risultato


# --- Elenchi in tabella (stesso bottone Esporta ovunque) -------------------------------------

@router.get("/auth/users/export")
def esporta_utenti(formato: str = "csv", pagina: str = "A4", db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    uffici = {uid: nome for uid, nome in db.query(UserGroup.user_id, Group.name).join(Group, Group.id == UserGroup.group_id).all()}
    mansioni = {}
    for uid, nome in db.query(UserMansione.user_id, Mansione.name).join(Mansione, Mansione.id == UserMansione.mansione_id).all():
        mansioni.setdefault(uid, []).append(nome)
    colonne = ["Nome", "Email", "Permessi", "Stato", "Tipo", "Credenziali", "Data ingresso", "Ufficio", "Mansioni"]
    righe = [[u.full_name, u.email, permessi_testo(u), "attivo" if u.is_active else "disattivato", "esterno" if u.is_external else "interno",
              "dominio" if u.origine_credenziali != "locale" else "locali", u.data_ingresso, uffici.get(u.id, ""), "; ".join(sorted(mansioni.get(u.id, [])))]
             for u in sorted(db.query(User).all(), key=lambda u: (u.full_name or "").casefold())]   # il nome e' cifrato: si ordina qui
    return esporta(formato, "utenti", "Utenti", colonne, righe, pagina)


@router.get("/corsi-export/elenco")
def esporta_corsi(formato: str = "csv", pagina: str = "A4", db: Session = Depends(get_db), user=Depends(require_training_admin)):
    from ..services.etichette import etichette_del_corso
    colonne = ["Titolo", "Etichette", "Validità (mesi)", "Rinnovo automatico", "Test finale", "Auto-iscrizione", "Versione", "Stato"]
    righe = [[c.titolo, "; ".join(f"{e.famiglia.nome}: {e.nome}" for e in etichette_del_corso(db, c.id)), c.validita_mesi, f"{c.rinnovo_giorni_anticipo} gg prima" if c.rinnovo_automatico else "", c.ha_test_finale,
              ("con approvazione" if c.richiedi_approvazione_responsabile else "sì") if c.permetti_autoiscrizione else "", c.versione,
              "attivo" if c.is_active else "disattivato"] for c in db.query(Corso).order_by(Corso.titolo).all()]
    return esporta(formato, "corsi", "Catalogo corsi", colonne, righe, pagina)


@router.get("/admin/gruppi-export")
def esporta_gruppi(formato: str = "csv", pagina: str = "A4", db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    gruppi = db.query(Group).all()
    per_id = {g.id: g for g in gruppi}
    utenti = {u.id: u.full_name for u in db.query(User).all()}
    membri = {}
    for gid, in db.query(UserGroup.group_id).all():
        membri[gid] = membri.get(gid, 0) + 1
    colonne = ["Ufficio", "Responsabile", "Persone", "Stato"]
    righe = [[svc._percorso_gruppo(g, per_id), utenti.get(g.responsabile_id, ""), membri.get(g.id, 0),
              "attivo" if g.is_active else "disattivato"] for g in gruppi]
    righe.sort(key=lambda r: r[0].lower())
    return esporta(formato, "gruppi", "Uffici", colonne, righe, pagina)


@router.get("/corsi-export/percorsi")
def esporta_percorsi(formato: str = "csv", pagina: str = "A4", db: Session = Depends(get_db), user=Depends(require_training_admin)):
    titoli = {c.id: c.titolo for c in db.query(Corso).all()}
    colonne = ["Percorso", "Assegnazione", "Passi (in ordine)", "Stato"]
    righe = [[p.nome, p.trigger_tipo.value, " → ".join(titoli.get(s.corso_id, "?") for s in sorted(p.steps, key=lambda x: x.ordine)),
              "attivo" if p.is_active else "disattivato"] for p in db.query(PercorsoFormativo).order_by(PercorsoFormativo.nome).all()]
    return esporta(formato, "percorsi", "Percorsi formativi", colonne, righe, pagina)


@router.get("/organizzazioni-export/elenco")
def esporta_organizzazioni(formato: str = "csv", pagina: str = "A4", db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    colonne = ["Ragione sociale", "Tipo", "Partita IVA", "Accreditamento", "Referente", "Email", "Telefono"]
    righe = [[o.ragione_sociale, o.tipo, o.partita_iva, o.accreditamento, o.referente, o.email, o.telefono]
             for o in db.query(Organizzazione).order_by(Organizzazione.ragione_sociale).all()]
    return esporta(formato, "societa_formazione", "Società di formazione", colonne, righe, pagina)
