"""Operazioni di manutenzione della cifratura: controllo all'avvio, conversione dei dati esistenti, cambio chiave."""
import os

from sqlalchemy.orm import Session

from ..config import settings
from ..models.azienda import Azienda
from . import cifratura as c

CARTELLE = ["/app/uploads", "/app/videos"]
VERIFICA = "verifica-cifratura"


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
                if not nome.endswith(".parte"):
                    yield os.path.join(cartella, nome)


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
            dati = c.leggi_file(p)
            c.scrivi_file(p, dati, cifra=(modo != "decifra"))
            fatti += 1
        except Exception as e:   # un file rotto non ferma la conversione degli altri
            errori.append(f"{p}: {e}")
    return {"convertiti": fatti, "saltati": saltati, "errori": errori}


def converti_db(db: Session, modo: str) -> dict:
    """Segreti nel database: chiave VAPID e verifica della chiave."""
    a = _azienda(db)
    toccati = []
    if a.vapid_private_key:
        chiaro = c.decifra_testo(a.vapid_private_key)
        if modo == "decifra":
            nuovo = chiaro
        elif modo == "cifra" or not c.testo_con_chiave_corrente(a.vapid_private_key):
            nuovo = c.cifra_testo(chiaro)
        else:
            nuovo = a.vapid_private_key
        if nuovo != a.vapid_private_key:
            a.vapid_private_key = nuovo
            toccati.append("vapid_private_key")
    if modo == "ruota" and c.attiva():
        a.cifratura_verifica = c.cifra_testo(VERIFICA)
        toccati.append("verifica")
    db.commit()
    return {"campi": toccati}


def disattiva(db: Session) -> str:
    """Toglie il marcatore 'cifratura usata'. Solo se non resta nulla di cifrato."""
    resto = riepilogo()
    a = _azienda(db)
    if resto["cifrato"] or resto["altra_chiave"] or c.testo_e_cifrato(a.vapid_private_key):
        raise ErroreAvvio("Ci sono ancora dati cifrati: esegui prima 'decifra'.")
    a.cifratura_verifica = None
    db.commit()
    return "Cifratura disattivata: ora puoi togliere CHIAVE_CIFRATURA."


def stato(db: Session) -> dict:
    a = db.query(Azienda).first()
    return {
        "chiave_presente": c.attiva(),
        "id_chiave": c.id_chiave_corrente(),
        "obbligatoria": bool(settings.CIFRATURA_OBBLIGATORIA),
        "usata": bool(a and a.cifratura_verifica),
        "file": riepilogo(),
        "vapid_cifrata": bool(a and c.testo_e_cifrato(a.vapid_private_key)),
    }
