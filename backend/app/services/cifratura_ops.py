"""Operazioni di manutenzione della cifratura: controllo all'avvio, conversione dei dati esistenti, cambio chiave."""
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..models.azienda import Azienda
from . import cifratura as c

# Esclusi i file temporanei della conversione dei video: ffmpeg li legge in chiaro e il sistema li elimina da solo.
ESCLUSI = ("/lavoro/", "/originali/")
CARTELLE = ["/app/uploads", "/app/videos"]
VERIFICA = "verifica-cifratura"
# Dati personali nel database (colonne di tipo TestoCifrato): tabella -> colonne.
COLONNE_PERSONALI = {
    "users": ("email", "nome", "cognome"),
    "organizzazioni": ("referente", "email", "telefono"),
    "audit_log": ("user_email", "ip_address", "detail"),
}
# I nomi di tabella e colonna nelle query SQL qui sotto vengono solo da COLONNE_PERSONALI (costante interna): nessun valore dell'utente (nosec B608).
LOTTO = 1000
RIGHE_REGISTRO_NELLO_STATO = 10000   # la pagina Stato conta solo le piu' recenti: il registro puo' avere milioni di righe


class ErroreAvvio(Exception):
    pass


def _azienda(db: Session) -> Azienda:
    a = db.query(Azienda).first()
    if not a:
        a = Azienda()
        db.add(a)
        db.flush()
    return a


def controlla_avvio(db: Session):
    """Impedisce di avviare la piattaforma in modo che scriva dati con la chiave sbagliata o senza chiave dopo
    che la cifratura e' stata usata: sarebbe un archivio a meta' cifrato e in parte illeggibile."""
    a = _azienda(db)
    if a.cifratura_verifica:
        if not c.attiva():
            raise ErroreAvvio("La cifratura e' stata attivata su questa installazione ma CHIAVE_CIFRATURA non e' impostata. "
                              "Rimetti la chiave (o, per disattivare la cifratura, decifra i dati con 'python -m app.cifratura_cli decifra' "
                              "e poi 'disattiva').")
        try:
            ok = c.decifra_testo(a.cifratura_verifica) == VERIFICA
        except c.ErroreCifratura as e:
            raise ErroreAvvio(f"CHIAVE_CIFRATURA non corrisponde ai dati: {e}. Se hai cambiato chiave, metti la vecchia in "
                              "CHIAVI_CIFRATURA_PRECEDENTI.")
        if not ok:
            raise ErroreAvvio("CHIAVE_CIFRATURA non corrisponde ai dati cifrati.")
    elif c.attiva():
        a.cifratura_verifica = c.cifra_testo(VERIFICA)   # prima attivazione
        db.commit()
    elif settings.CIFRATURA_OBBLIGATORIA:
        raise ErroreAvvio("CIFRATURA_OBBLIGATORIA e' attiva ma CHIAVE_CIFRATURA non e' impostata.")
    else:
        db.commit()


def _file_da_controllare(cartelle):
    for radice in cartelle:
        for cartella, _, nomi in os.walk(radice):
            for nome in nomi:
                percorso = os.path.join(cartella, nome)
                if not nome.endswith(".parte") and not any(x in percorso + "/" for x in ESCLUSI):
                    yield percorso


def riepilogo(cartelle=None) -> dict:
    conta = {"chiaro": 0, "cifrato": 0, "altra_chiave": 0, "illeggibili": 0}
    for p in _file_da_controllare(cartelle or CARTELLE):
        try:
            conta[c.stato_file(p)] += 1
        except OSError:
            conta["illeggibili"] += 1
    return conta


def converti_file(modo: str, cartelle=None) -> dict:
    """modo: 'cifra' (i file in chiaro), 'decifra' (tutti), 'ruota' (quelli con un'altra chiave)."""
    fatti, saltati, errori = 0, 0, []
    for p in _file_da_controllare(cartelle or CARTELLE):
        try:
            stato = c.stato_file(p)
            if (modo == "cifra" and stato != "chiaro") or (modo == "decifra" and stato == "chiaro") or (modo == "ruota" and stato != "altra_chiave"):
                saltati += 1
                continue
            with c.Scrittore(p, cifra=(modo != "decifra")) as s:   # a blocchi: mai un file intero in memoria
                for pezzo in c.leggi_a_blocchi(p):
                    s.scrivi(pezzo)
            fatti += 1
        except Exception as e:   # un file rotto non ferma la conversione degli altri
            errori.append(f"{p}: {e}")
    return {"convertiti": fatti, "saltati": saltati, "errori": errori}


def _nuovo_valore(valore, modo: str):
    """Il valore da scrivere per il modo scelto (uguale a quello attuale se non c'e' nulla da fare)."""
    if valore is None or valore == "":
        return valore
    chiaro = c.decifra_testo(valore)
    if modo == "decifra":
        return chiaro
    if modo == "cifra" or not c.testo_con_chiave_corrente(valore):
        return c.cifra_testo(chiaro)
    return valore


def converti_dati_personali(db: Session, modo: str) -> dict:
    """Cifra, decifra o ricifra le colonne dei dati personali, a lotti (il registro attivita' puo' essere grande).
    Lavora sul testo grezzo del database: non passa dal tipo cifrato, che farebbe la conversione da solo."""
    conteggi = {}
    for tabella, colonne in COLONNE_PERSONALI.items():
        modificati, ultimo = 0, None
        while True:
            filtro = "WHERE id > :u" if ultimo else ""
            righe = db.execute(text(f"SELECT id, {', '.join(colonne)} FROM {tabella} {filtro} ORDER BY id LIMIT {LOTTO}"),  # nosec B608
                               {"u": ultimo} if ultimo else {}).fetchall()
            if not righe:
                break
            for riga in righe:
                nuovi = {col: _nuovo_valore(riga[i + 1], modo) for i, col in enumerate(colonne)}
                cambiati = {col: v for i, (col, v) in enumerate(nuovi.items()) if v != riga[i + 1]}
                if cambiati:
                    db.execute(text(f"UPDATE {tabella} SET {', '.join(f'{col} = :{col}' for col in cambiati)} WHERE id = :id"),  # nosec B608
                               {**cambiati, "id": riga[0]})
                    modificati += 1
            db.commit()
            ultimo = righe[-1][0]
        conteggi[tabella] = modificati
    return conteggi


def riepilogo_dati_personali(db: Session, veloce: bool = False) -> dict:
    """Quanti valori dei dati personali sono cifrati e quanti in chiaro. Con `veloce` (pagina Stato) del registro
    attivita', che puo' avere milioni di righe, si guardano solo le ultime 10000."""
    chiaro = cifrato = 0
    for tabella, colonne in COLONNE_PERSONALI.items():
        origine = f"(SELECT * FROM {tabella} ORDER BY created_at DESC LIMIT {RIGHE_REGISTRO_NELLO_STATO}) t" if veloce and tabella == "audit_log" else tabella  # nosec B608
        for col in colonne:
            n_cifrati, n_totali = db.execute(text(
                f"SELECT count(*) FILTER (WHERE {col} LIKE '{c.PREFISSO_TESTO}%'), count({col}) FROM {origine}")).one()  # nosec B608
            cifrato += n_cifrati
            chiaro += n_totali - n_cifrati
    return {"chiaro": chiaro, "cifrato": cifrato}


def converti_db(db: Session, modo: str) -> dict:
    """Segreti e dati personali nel database: chiave VAPID, chiave delle impronte, dati personali, verifica della chiave."""
    a = _azienda(db)
    toccati = []
    for campo in ("vapid_private_key", "impronta_chiave"):
        attuale = getattr(a, campo)
        nuovo = _nuovo_valore(attuale, modo)
        if nuovo != attuale:
            setattr(a, campo, nuovo)
            toccati.append(campo)
    db.commit()
    dati_personali = converti_dati_personali(db, modo)
    if modo == "ruota" and c.attiva():
        a.cifratura_verifica = c.cifra_testo(VERIFICA)
        toccati.append("verifica")
    db.commit()
    return {"campi": toccati, "dati_personali": dati_personali}


def disattiva(db: Session) -> str:
    """Toglie il marcatore 'cifratura usata'. Solo se non resta nulla di cifrato."""
    resto = riepilogo()
    a = _azienda(db)
    if (resto["cifrato"] or resto["altra_chiave"] or c.testo_e_cifrato(a.vapid_private_key) or c.testo_e_cifrato(a.impronta_chiave)
            or riepilogo_dati_personali(db)["cifrato"]):
        raise ErroreAvvio("Ci sono ancora dati cifrati: esegui prima 'decifra'.")
    a.cifratura_verifica = None
    db.commit()
    return "Cifratura disattivata: ora puoi togliere CHIAVE_CIFRATURA."


def stato(db: Session, completo: bool = False) -> dict:
    """`completo`: conta tutto il registro attivita' (lo strumento da riga di comando); la pagina Stato conta le ultime 10000 righe."""
    a = db.query(Azienda).first()
    return {
        "chiave_presente": c.attiva(),
        "id_chiave": c.id_chiave_corrente(),
        "obbligatoria": bool(settings.CIFRATURA_OBBLIGATORIA),
        "usata": bool(a and a.cifratura_verifica),
        "file": riepilogo(),
        "vapid_cifrata": bool(a and c.testo_e_cifrato(a.vapid_private_key)),
        "dati_personali": riepilogo_dati_personali(db, veloce=not completo),
    }
