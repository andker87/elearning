"""2.12.0: spazi di lavoro, «Da gestire», contatori, riepilogo dell'amministrazione, dati della Home."""
from datetime import timedelta

from app.models.edizione import ModalitaErogazione as M, StatoEdizione as SE
from app.models.iscrizione import StatoIscrizione as S
from app.models.password_reset import RichiestaResetPassword
from app.models.richiesta_corso import RichiestaCorso
from app.models.richiesta_iscrizione import RichiestaIscrizione
from app.models.video import StatoVideo, VideoContenuto, VideoProgresso
from app.api import spazi as spazi_api

from conftest import adesso


def _azzera_cache():
    spazi_api._attese_cache.update({"t": 0.0, "valore": None})


def test_da_gestire_raccoglie_tutto_e_i_contatori_lo_contano(client, auth, formazione, utente, admin, crea_utente, db, crea_corso, crea_edizione, crea_iscrizione):
    _azzera_cache()
    c = crea_corso("Antincendio"); d = crea_corso("Primo soccorso")
    finita = crea_edizione(c, stato=SE.pianificata, data_inizio=adesso() - timedelta(days=3), data_fine=adesso() - timedelta(days=2))
    crea_iscrizione(finita, utente)
    futura = crea_edizione(d, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=5))
    db.add(RichiestaIscrizione(edizione_id=futura.id, user_id=utente.id, richiedente_id=utente.id))
    db.add(RichiestaCorso(richiedente_id=admin.id, argomento="Carrelli elevatori"))
    # una persona in un percorso aspetta una sessione di un corso che non ne ha
    senza = crea_corso("Sicurezza specifica")
    p = client.post("/api/percorsi", headers=auth(formazione), json={"nome": "Neoassunti", "modalita": "libero", "steps": [{"corso_id": str(senza.id), "ordine": 1}]}).json()
    client.post(f"/api/percorsi/{p['id']}/assegna", headers=auth(formazione), json=[str(crea_utente("nuovo@t.it").id)])
    db.commit()
    r = client.get("/api/da-gestire", headers=auth(formazione)).json()
    assert [x["corso_titolo"] for x in r["sessioni_da_chiudere"]] == ["Antincendio"] and r["sessioni_da_chiudere"][0]["n_iscritti"] == 1
    assert [x["corso_titolo"] for x in r["richieste_iscrizione"]] == ["Primo soccorso"] and r["richieste_iscrizione"][0]["autorichiesta"] is True
    assert [x["titolo"] for x in r["richieste_corsi"]] == ["Carrelli elevatori"]
    assert r["percorsi"] == [{"corso_id": str(senza.id), "corso_titolo": "Sicurezza specifica", "in_attesa": 1, "da_rifare": 0, "percorsi": ["Neoassunti"]}]
    assert r["totale"] == 4
    assert client.get("/api/contatori", headers=auth(formazione)).json() == {"gestione": 4, "amministrazione": None, "team": None}
    assert client.get("/api/da-gestire", headers=auth(utente)).status_code == 403


def test_contatori_per_ruolo(client, auth, utente, admin, crea_utente, crea_ufficio, db, crea_corso, crea_edizione):
    from app.models.autoiscrizione import AutoIscrizioneRichiesta
    _azzera_cache()
    assert client.get("/api/contatori", headers=auth(utente)).json() == {"gestione": None, "amministrazione": None, "team": None}
    capo = crea_utente("capo@t.it", nome="Capo", cognome="Ufficio")
    crea_ufficio("Produzione", membri=[capo, utente], responsabile=capo)
    e = crea_edizione(crea_corso("Corso"), stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3))
    db.add(AutoIscrizioneRichiesta(edizione_id=e.id, user_id=utente.id)); db.commit()
    assert client.get("/api/contatori", headers=auth(capo)).json()["team"] == 1
    db.add(RichiestaResetPassword(user_id=utente.id)); db.commit()
    c = client.get("/api/contatori", headers=auth(admin)).json()
    assert c["amministrazione"] == 1 and c["gestione"] == 0               # l'admin ha anche lo spazio Gestione


def test_riepilogo_dell_amministrazione(client, auth, admin, formazione, utente, crea_utente, crea_ufficio, db):
    crea_ufficio("Produzione", membri=[utente])
    crea_utente("senzaufficio@t.it")
    r = client.get("/api/amministrazione/riepilogo", headers=auth(admin))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["persone"]["attive"] >= 3 and d["persone"]["senza_ufficio"] >= 1 and d["richieste_password"] == 0
    assert set(d["lavori"]) == {"sync_entra", "notifiche_giornaliere", "percorsi_iscrizioni", "rinnovi_automatici"}
    assert "smtp" in d and "storage" in d
    assert client.get("/api/amministrazione/riepilogo", headers=auth(formazione)).status_code == 403


def test_la_home_sa_quanto_video_hai_visto(client, auth, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    v = VideoContenuto(titolo="Video", stato=StatoVideo.pronto, durata_secondi=200); db.add(v); db.commit()
    e = crea_edizione(crea_corso("Comunicazione"), stato=SE.pianificata, modalita=M.video, video_id=v.id, data_inizio=None, sempre_aperta=True)
    i = crea_iscrizione(e, utente)
    db.add(VideoProgresso(iscrizione_id=i.id, secondo_massimo_raggiunto=50)); db.commit()
    mia = client.get("/api/edizioni/mie/iscrizioni", headers=auth(utente)).json()[0]
    assert mia["video_pct"] == 25.0 and mia["video_disponibile"] is True and mia["edizione_sempre_aperta"] is True
    p = crea_edizione(crea_corso("In aula"), stato=SE.pianificata, data_inizio=adesso() + timedelta(days=2), luogo="Sala Verde")
    crea_iscrizione(p, utente)
    aula = next(x for x in client.get("/api/edizioni/mie/iscrizioni", headers=auth(utente)).json() if x["corso_titolo"] == "In aula")
    assert aula["video_pct"] is None and aula["edizione_luogo"] == "Sala Verde"
