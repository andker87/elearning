"""Caricamento di molte righe in una sola query, per non fare una richiesta al database per ogni riga di un elenco."""


def per_id(db, modello, ids) -> dict:
    """{str(id): oggetto} per gli id dati (quelli mancanti o nulli sono ignorati)."""
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {str(r.id): r for r in db.query(modello).filter(modello.id.in_(ids)).all()}
