import inspect
from collections import Counter
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from ..services.etichette import corsi_con_etichette
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from ..models.user import User
from ..models.corso import Corso
from ..models.edizione import Edizione, EdizioneDocente, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.test import Test, TentativoTest, MomentoTest, Gradimento, GradimentoDocente
from ..models.azienda import Azienda
from ..services.gerarchia import persone_ufficio_e_sottouffici
from ..services.export import esporta
from .deps import require_training_admin

router = APIRouter(prefix="/api/dashboard/kpi", tags=["dashboard-kpi"])

def _media(valori: List[float], cifre=1):
    return round(sum(valori) / len(valori), cifre) if valori else None

def _ore_edizione(e: Edizione) -> float:
    """Non tutte le modalità hanno ore dichiarate esplicitamente (solo
    'esterna' le richiede) - per le altre si stima dalla durata della
    sessione, quando nota. Approssimazione dichiarata, non un dato certo."""
    if e.ore_dichiarate:
        return float(e.ore_dichiarate)
    if e.data_inizio and e.data_fine:
        return max(0.0, (e.data_fine - e.data_inizio).total_seconds() / 3600)
    return 0.0

def _edizioni_filtrate(db: Session, corso_id: Optional[str], docente_id: Optional[str],
                        da: Optional[datetime], a: Optional[datetime], etichette: Optional[List[str]] = None) -> List[Edizione]:
    q = db.query(Edizione)
    if corso_id:
        q = q.filter(Edizione.corso_id == corso_id)
    ammessi = corsi_con_etichette(db, etichette)  # None = nessun filtro per etichetta
    if ammessi is not None:
        q = q.filter(Edizione.corso_id.in_(ammessi or [None]))
    if docente_id:
        q = q.join(EdizioneDocente, EdizioneDocente.edizione_id == Edizione.id).filter(EdizioneDocente.user_id == docente_id)
    if da:
        q = q.filter(Edizione.data_inizio.isnot(None), Edizione.data_inizio >= da)
    if a:
        q = q.filter(Edizione.data_inizio.isnot(None), Edizione.data_inizio <= a)
    return q.all()

def _iscrizioni_di(db: Session, edizioni_ids: List, ufficio_id: Optional[str]) -> List[Iscrizione]:
    if not edizioni_ids:
        return []
    q = db.query(Iscrizione).filter(Iscrizione.edizione_id.in_(edizioni_ids), Iscrizione.stato != StatoIscrizione.annullato)
    if ufficio_id:
        persone_ids = [p.id for p in persone_ufficio_e_sottouffici(db, ufficio_id)]
        q = q.filter(Iscrizione.user_id.in_(persone_ids))
    return q.all()

def _punteggi_ultimo_tentativo(db: Session, iscrizione_ids: List, momento: MomentoTest) -> List[float]:
    if not iscrizione_ids:
        return []
    rows = (
        db.query(TentativoTest)
        .join(Test, TentativoTest.test_id == Test.id)
        .filter(TentativoTest.iscrizione_id.in_(iscrizione_ids), Test.momento == momento,
                TentativoTest.punteggio_pct.isnot(None))
        .order_by(TentativoTest.iscrizione_id, TentativoTest.completato_at.desc())
        .all()
    )
    ultimo: dict = {}
    for r in rows:
        if r.iscrizione_id not in ultimo:
            ultimo[r.iscrizione_id] = r.punteggio_pct
    return list(ultimo.values())

def _metriche(db: Session, edizioni: List[Edizione], ufficio_id: Optional[str] = None,
              docente_focus_id: Optional[str] = None) -> dict:
    edizioni_ids = [e.id for e in edizioni]
    iscr = _iscrizioni_di(db, edizioni_ids, ufficio_id)
    iscr_ids = [i.id for i in iscr]

    completate = [i for i in iscr if i.stato == StatoIscrizione.completato]
    non_completate = [i for i in iscr if i.stato == StatoIscrizione.non_completato]
    decise = completate + non_completate
    tasso_completamento_pct = _media([100.0 if i.stato == StatoIscrizione.completato else 0.0 for i in decise]) if decise else None

    punteggio_finale_medio = _media(_punteggi_ultimo_tentativo(db, iscr_ids, MomentoTest.finale))
    punteggio_iniziale_medio = _media(_punteggi_ultimo_tentativo(db, iscr_ids, MomentoTest.iniziale))
    delta_pre_post = (round(punteggio_finale_medio - punteggio_iniziale_medio, 1)
                       if punteggio_finale_medio is not None and punteggio_iniziale_medio is not None else None)

    gradimenti = db.query(Gradimento).filter(Gradimento.iscrizione_id.in_(iscr_ids)).all() if iscr_ids else []
    gradimento_corso_medio = _media([g.voto_corso for g in gradimenti], 2)

    gradimento_ids = [g.id for g in gradimenti]
    voti_docenti_q = db.query(GradimentoDocente).filter(GradimentoDocente.gradimento_id.in_(gradimento_ids)) if gradimento_ids else None
    if voti_docenti_q is not None and docente_focus_id:
        voti_docenti_q = voti_docenti_q.filter(GradimentoDocente.docente_id == docente_focus_id)
    voti_docenti = voti_docenti_q.all() if voti_docenti_q is not None else []
    gradimento_docenti_medio = _media([v.voto for v in voti_docenti], 2)

    ore_erogate = sum(_ore_edizione(e) for e in edizioni if e.stato == StatoEdizione.chiusa)

    return {
        "n_edizioni": len(edizioni), "n_iscrizioni": len(iscr),
        "n_completati": len(completate), "n_non_completati": len(non_completate),
        "tasso_completamento_pct": tasso_completamento_pct,
        "punteggio_test_medio": punteggio_finale_medio,
        "punteggio_test_iniziale_medio": punteggio_iniziale_medio,
        "delta_pre_post": delta_pre_post,
        "gradimento_corso_medio": gradimento_corso_medio,
        "gradimento_docenti_medio": gradimento_docenti_medio,
        "ore_erogate": round(ore_erogate, 1),
    }

@router.get("/docenti")
def lista_docenti(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    righe = db.query(EdizioneDocente.user_id).distinct().all()
    ids = [r[0] for r in righe]
    docenti = sorted(db.query(User).filter(User.id.in_(ids)).all(), key=lambda u: (u.full_name or "").casefold()) if ids else []
    return [{"id": str(d.id), "full_name": d.full_name} for d in docenti]

@router.get("/riepilogo")
def riepilogo(corso_id: Optional[str] = Query(None), docente_id: Optional[str] = Query(None),
              ufficio_id: Optional[str] = Query(None), da: Optional[datetime] = Query(None),
              a: Optional[datetime] = Query(None), etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db),
              user=Depends(require_training_admin)):
    edizioni = _edizioni_filtrate(db, corso_id, docente_id, da, a, etichette)
    return _metriche(db, edizioni, ufficio_id, docente_focus_id=docente_id)

@router.get("/per-corso")
def per_corso(docente_id: Optional[str] = Query(None), ufficio_id: Optional[str] = Query(None),
              da: Optional[datetime] = Query(None), a: Optional[datetime] = Query(None),
              etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db), user=Depends(require_training_admin)):
    out = []
    for corso in db.query(Corso).order_by(Corso.titolo).all():
        edizioni = _edizioni_filtrate(db, str(corso.id), docente_id, da, a, etichette)
        if not edizioni:
            continue
        m = _metriche(db, edizioni, ufficio_id, docente_focus_id=docente_id)
        out.append({"corso_id": str(corso.id), "corso_titolo": corso.titolo, **m})
    return out

@router.get("/per-docente")
def per_docente(corso_id: Optional[str] = Query(None), ufficio_id: Optional[str] = Query(None),
                 da: Optional[datetime] = Query(None), a: Optional[datetime] = Query(None),
                 etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db), user=Depends(require_training_admin)):
    edizioni_base = _edizioni_filtrate(db, corso_id, None, da, a, etichette)
    edizioni_ids = [e.id for e in edizioni_base]
    if not edizioni_ids:
        return []
    assoc = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id.in_(edizioni_ids)).all()
    docenti_ids = sorted({str(a.user_id) for a in assoc})
    edizioni_per_docente: dict = {}
    for a in assoc:
        edizioni_per_docente.setdefault(str(a.user_id), set()).add(a.edizione_id)

    out = []
    for did in docenti_ids:
        docente = db.query(User).filter(User.id == did).first()
        if not docente:
            continue
        sue_edizioni = [e for e in edizioni_base if e.id in edizioni_per_docente[did]]
        m = _metriche(db, sue_edizioni, ufficio_id, docente_focus_id=did)
        out.append({"docente_id": did, "docente_nome": docente.full_name, **m})
    out.sort(key=lambda r: r["docente_nome"])
    return out

@router.get("/andamento")
def andamento(corso_id: Optional[str] = Query(None), docente_id: Optional[str] = Query(None),
              ufficio_id: Optional[str] = Query(None), da: Optional[datetime] = Query(None),
              a: Optional[datetime] = Query(None), etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db),
              user=Depends(require_training_admin)):
    """Andamento mensile: raggruppa le edizioni per mese di svolgimento
    (data_inizio) e calcola le stesse metriche per ciascun mese - serve a
    vedere un trend, non uno snapshot."""
    edizioni = _edizioni_filtrate(db, corso_id, docente_id, da, a, etichette)
    per_mese: dict = {}
    for e in edizioni:
        if not e.data_inizio:
            continue
        chiave = e.data_inizio.strftime("%Y-%m")
        per_mese.setdefault(chiave, []).append(e)
    out = []
    for mese in sorted(per_mese.keys()):
        m = _metriche(db, per_mese[mese], ufficio_id, docente_focus_id=docente_id)
        out.append({"mese": mese, **m})
    return out

@router.get("/confronto-edizioni")
def confronto_edizioni(corso_id: str = Query(...), docente_id: Optional[str] = Query(None),
                        ufficio_id: Optional[str] = Query(None), da: Optional[datetime] = Query(None),
                        a: Optional[datetime] = Query(None), etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db),
                        user=Depends(require_training_admin)):
    edizioni = _edizioni_filtrate(db, corso_id, docente_id, da, a, etichette)
    out = []
    for e in sorted(edizioni, key=lambda x: (x.data_inizio is None, x.data_inizio.timestamp() if x.data_inizio else 0)):
        m = _metriche(db, [e], ufficio_id, docente_focus_id=docente_id)
        iscr_ids = [i.id for i in _iscrizioni_di(db, [e.id], ufficio_id)]
        versioni = [i.versione_corso for i in db.query(Iscrizione).filter(
            Iscrizione.id.in_(iscr_ids), Iscrizione.stato == StatoIscrizione.completato,
            Iscrizione.versione_corso.isnot(None)).all()]
        versione_dominante = Counter(versioni).most_common(1)[0][0] if versioni else None
        out.append({
            "edizione_id": str(e.id), "data_inizio": e.data_inizio, "modalita": e.modalita,
            "versione_corso": versione_dominante, **m,
        })
    return out

@router.get("/confronto-versioni")
def confronto_versioni(corso_id: str = Query(...), ufficio_id: Optional[str] = Query(None),
                        db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Confronta le versioni del contenuto (sezione versionamento) invece
    delle singole edizioni: solo su chi ha completato, perché la versione è
    uno snapshot preso al completamento (vedi Iscrizione.versione_corso)."""
    edizioni_ids = [e.id for e in db.query(Edizione).filter(Edizione.corso_id == corso_id).all()]
    iscr = _iscrizioni_di(db, edizioni_ids, ufficio_id)
    completate = [i for i in iscr if i.stato == StatoIscrizione.completato and i.versione_corso is not None]
    per_versione: dict = {}
    for i in completate:
        per_versione.setdefault(i.versione_corso, []).append(i)
    out = []
    for versione in sorted(per_versione.keys()):
        gruppo = per_versione[versione]
        ids = [i.id for i in gruppo]
        punteggio_medio = _media(_punteggi_ultimo_tentativo(db, ids, MomentoTest.finale))
        gradimenti = db.query(Gradimento).filter(Gradimento.iscrizione_id.in_(ids)).all()
        gradimento_medio = _media([g.voto_corso for g in gradimenti], 2)
        out.append({
            "versione": versione, "n_completati": len(gruppo),
            "punteggio_test_medio": punteggio_medio, "gradimento_corso_medio": gradimento_medio,
        })
    return out

_VISTE = {
    "per-corso": (per_corso, ["corso_titolo", "n_edizioni", "n_iscrizioni", "tasso_completamento_pct",
                               "punteggio_test_medio", "delta_pre_post", "gradimento_corso_medio",
                               "gradimento_docenti_medio", "ore_erogate"]),
    "per-docente": (per_docente, ["docente_nome", "n_edizioni", "n_iscrizioni", "tasso_completamento_pct",
                                    "punteggio_test_medio", "gradimento_corso_medio", "gradimento_docenti_medio",
                                    "ore_erogate"]),
    "andamento": (andamento, ["mese", "n_edizioni", "n_completati", "tasso_completamento_pct",
                                "punteggio_test_medio", "gradimento_corso_medio"]),
    "confronto-edizioni": (confronto_edizioni, ["edizione_id", "data_inizio", "modalita", "versione_corso",
                                                  "n_iscrizioni", "tasso_completamento_pct", "punteggio_test_medio",
                                                  "gradimento_corso_medio", "gradimento_docenti_medio"]),
    "confronto-versioni": (confronto_versioni, ["versione", "n_completati", "punteggio_test_medio", "gradimento_corso_medio"]),
}
_VISTE_CORSO_OBBLIGATORIO = {"confronto-edizioni", "confronto-versioni"}

@router.get("/export")
def export_vista(vista: str = Query(...), formato: str = Query("csv"), pagina: str = Query("A4"),
                  corso_id: Optional[str] = Query(None), docente_id: Optional[str] = Query(None),
                  ufficio_id: Optional[str] = Query(None), da: Optional[datetime] = Query(None),
                  a: Optional[datetime] = Query(None), etichette: Optional[List[str]] = Query(None),
                  db: Session = Depends(get_db), user=Depends(require_training_admin)):
    if vista not in _VISTE:
        raise HTTPException(400, f"Vista non valida: {vista}")
    if vista in _VISTE_CORSO_OBBLIGATORIO and not corso_id:
        raise HTTPException(400, "corso_id obbligatorio per questa vista")
    funzione, colonne = _VISTE[vista]
    # Ogni "vista" accetta solo un sottoinsieme di questi filtri (es. per_corso
    # non ha un proprio corso_id, confronto_versioni non ha docente_id) - si
    # passano solo quelli che la funzione accetta davvero, invece di un elenco
    # scritto a mano per vista che si disallinea facilmente dalle firme reali.
    disponibili = {"corso_id": corso_id, "docente_id": docente_id, "ufficio_id": ufficio_id,
                   "da": da, "a": a, "etichette": etichette, "db": db, "user": user}
    parametri_accettati = set(inspect.signature(funzione).parameters)
    kwargs = {k: v for k, v in disponibili.items() if k in parametri_accettati}
    righe_dati = funzione(**kwargs)
    righe = [[r.get(c, "") for c in colonne] for r in righe_dati]
    azienda = db.query(Azienda).first()
    return esporta(formato, f"kpi_{vista}", f"KPI formazione — {vista}", colonne, righe,
                   pagina, azienda.logo_path if azienda else None)
