"""2.5.0: durata di corsi e sessioni (ereditata dal corso, forzabile, congelata alla chiusura)."""
import pytest

from app.models.corso import Corso
from app.models.edizione import Edizione, StatoEdizione
from conftest import adesso
from app.services.durata import congela, durata_effettiva, ore_testo, durata_in_parole


def test_testi_della_durata():
    assert durata_in_parole(270) == "4 ore e 30 minuti" and durata_in_parole(60) == "1 ora" and durata_in_parole(45) == "45 minuti"
    assert durata_in_parole(61) == "1 ora e 1 minuto" and durata_in_parole(None) == "" and durata_in_parole(0) == ""
    assert ore_testo(480) == "8" and ore_testo(90) == "1,5" and ore_testo(100) == "1,67" and ore_testo(None) == ""


def test_il_corso_dichiara_la_durata_e_la_si_controlla(client, auth, formazione):
    ok = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Antincendio", "durata_minuti": 240})
    assert ok.status_code == 200 and ok.json()["durata_minuti"] == 240
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Senza durata"}).json()["durata_minuti"] is None
    for brutta in (0, -5, 100001):
        assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "X", "durata_minuti": brutta}).status_code == 422
    cid = ok.json()["id"]
    r = client.put(f"/api/corsi/{cid}", headers=auth(formazione), json={"titolo": "Antincendio", "durata_minuti": 300})
    assert r.status_code == 200 and r.json()["durata_minuti"] == 300


def sessione(client, auth, formazione, corso_id, **extra):
    return client.post("/api/edizioni", headers=auth(formazione), json={"corso_id": corso_id, "modalita": "presenza", **extra})


def test_la_sessione_eredita_la_durata_del_corso_e_si_puo_forzare(client, auth, formazione, crea_corso, db):
    c = crea_corso("Primo soccorso"); c.durata_minuti = 480; db.commit()
    cid = str(c.id)
    e = sessione(client, auth, formazione, cid).json()
    assert (e["durata_minuti"], e["durata_corso_minuti"], e["durata_effettiva_minuti"], e["durata_modificata"]) == (None, 480, 480, False)
    # la stessa durata del corso non e' «forzata»: la sessione continua a seguire il corso
    uguale = sessione(client, auth, formazione, cid, durata_minuti=480).json()
    assert uguale["durata_minuti"] is None and uguale["durata_modificata"] is False
    # una durata diversa e' una durata forzata
    forzata = sessione(client, auth, formazione, cid, durata_minuti=360).json()
    assert (forzata["durata_minuti"], forzata["durata_effettiva_minuti"], forzata["durata_modificata"]) == (360, 360, True)
    # se poi cambia la durata del corso, la sessione non forzata la segue, quella forzata no
    c.durata_minuti = 600; db.commit()
    assert client.get(f"/api/edizioni/{e['id']}", headers=auth(formazione)).json()["durata_effettiva_minuti"] == 600
    assert client.get(f"/api/edizioni/{forzata['id']}", headers=auth(formazione)).json()["durata_effettiva_minuti"] == 360
    # tornare alla durata del corso: si svuota il campo
    r = client.put(f"/api/edizioni/{forzata['id']}", headers=auth(formazione), json={"corso_id": cid, "modalita": "presenza", "durata_minuti": None})
    assert r.json()["durata_minuti"] is None and r.json()["durata_effettiva_minuti"] == 600
    assert sessione(client, auth, formazione, cid, durata_minuti=0).status_code == 422


def test_senza_durata_del_corso_la_sessione_puo_avere_la_sua(client, auth, formazione, crea_corso):
    cid = str(crea_corso("Senza durata").id)
    e = sessione(client, auth, formazione, cid, durata_minuti=90).json()
    assert (e["durata_corso_minuti"], e["durata_effettiva_minuti"], e["durata_modificata"]) == (None, 90, False)   # niente da cui differire: non e' «modificata»


def test_alla_chiusura_la_durata_si_congela(db, crea_corso, crea_edizione):
    c = crea_corso("Corso"); c.durata_minuti = 120; db.commit()
    e = crea_edizione(c, stato=StatoEdizione.pianificata)
    congela(e, c); db.commit()
    c.durata_minuti = 999; db.commit()                                                  # il corso cambia dopo
    db.refresh(e)
    assert e.durata_minuti == 120 and durata_effettiva(e, c) == 120                     # la sessione chiusa no
    f = crea_edizione(c, stato=StatoEdizione.pianificata); f.durata_minuti = 30; db.commit()
    congela(f, c)
    assert f.durata_minuti == 30                                                         # una durata forzata resta quella


def test_chiudendo_una_sessione_la_durata_va_nell_attestato_e_resta(client, auth, formazione, crea_corso, crea_edizione, crea_iscrizione, db, monkeypatch):
    from app.services import certificati as cert
    catturati = {}
    originale = cert.genera_pdf
    def finto(path, **kw):
        catturati.update(kw); return originale(path, **kw)
    monkeypatch.setattr(cert, "genera_pdf", finto)
    c = crea_corso("Antincendio"); c.durata_minuti = 150; db.commit()
    e = crea_edizione(c, stato=StatoEdizione.in_corso)
    u = db.query(__import__("app.models.user", fromlist=["User"]).User).first()
    i = crea_iscrizione(e, u)
    from app.models.evidenza import Evidenza, FonteEvidenza
    ora = adesso()
    db.add(Evidenza(iscrizione_id=i.id, fonte=FonteEvidenza.checkin_docente, inizio_at=ora, fine_at=ora)); db.commit()
    r = client.post(f"/api/edizioni/{e.id}/chiudi", headers=auth(formazione))
    assert r.status_code == 200, r.text
    assert catturati.get("durata") == "2 ore e 30 minuti"                                # sull'attestato
    db.expire_all()
    assert db.get(Edizione, e.id).durata_minuti == 150                                   # e congelata sulla sessione chiusa


def test_i_report_usano_la_durata(db, crea_corso, crea_edizione):
    from app.api.dashboard_kpi import _ore_edizione
    c = crea_corso("Corso"); c.durata_minuti = 90; db.commit()
    e = crea_edizione(c)
    assert _ore_edizione(e, c) == 1.5
    e.durata_minuti = 60
    assert _ore_edizione(e, c) == 1.0


def test_i_campi_per_i_filtri_dei_discenti(client, auth, admin, crea_utente, crea_ufficio):
    u = crea_utente("p@t.it")
    uff = crea_ufficio("Produzione", membri=[u])
    mid = client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"}).json()["id"]
    client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"mansione_ids": [mid]})
    riga = [x for x in client.get("/api/auth/users/simple", headers=auth(admin)).json() if x["email"] == "p@t.it"][0]
    assert riga["ufficio_id"] == str(uff.id) and riga["mansione_ids"] == [mid]
