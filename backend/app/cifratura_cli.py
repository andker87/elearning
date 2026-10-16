"""Strumento da riga di comando per la cifratura:
    docker compose exec backend python -m app.cifratura_cli <comando>

    genera-chiave   stampa una nuova chiave (da mettere in CHIAVE_CIFRATURA; conservala in un luogo sicuro: senza, i dati cifrati sono persi)
    stato           mostra quanti file sono cifrati, in chiaro o con un'altra chiave
    cifra           cifra i file e i segreti ancora in chiaro
    decifra         riporta tutto in chiaro (emergenza o disattivazione)
    ruota           ricifica con la chiave corrente quanto e' cifrato con una chiave precedente
    disattiva       dopo 'decifra': toglie il marcatore, cosi' la piattaforma riparte senza chiave
"""
import json
import sys

from .database import SessionLocal
from .services import cifratura as c
from .services import cifratura_ops as ops


def main(argv=None):
    comando = (argv or sys.argv[1:] or ["aiuto"])[0]
    if comando == "genera-chiave":
        print(c.genera_chiave())
        return 0
    if comando not in ("stato", "cifra", "decifra", "ruota", "disattiva"):
        print(__doc__)
        return 0 if comando == "aiuto" else 2
    if comando in ("cifra", "ruota") and not c.attiva():
        print("CHIAVE_CIFRATURA non e' impostata.")
        return 2
    db = SessionLocal()
    try:
        if comando == "stato":
            risultato = ops.stato(db)
        elif comando == "disattiva":
            risultato = ops.disattiva(db)
        else:
            if comando == "decifra" and not c._chiavi_note():
                print("Serve la chiave (CHIAVE_CIFRATURA) per decifrare.")
                return 2
            risultato = {"file": ops.converti_file(comando), "database": ops.converti_db(db, comando)}
        print(json.dumps(risultato, ensure_ascii=False, indent=2) if not isinstance(risultato, str) else risultato)
        errori = risultato.get("file", {}).get("errori") if isinstance(risultato, dict) else None
        return 1 if errori else 0
    except ops.ErroreAvvio as e:
        print(f"Errore: {e}")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
