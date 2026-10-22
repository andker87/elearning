"""2.12.1: copertine dei corsi."""
import io
import os

import pytest
from PIL import Image

from app.models.corso import Corso
from app.models.edizione import StatoEdizione as SE
from app.services import copertine as svc
from app.services import cifratura


@pytest.fixture(autouse=True)
def cartella(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "CARTELLA", str(tmp_path / "copertine"))


def immagine(larghezza=1600, altezza=900, formato="PNG", colore=(20, 120, 100), **kw):
    buf = io.BytesIO()
    Image.new("RGB", (larghezza, altezza), colore).save(buf, formato, **kw)
    return buf.getvalue()


def carica(client, auth, utente, corso, dati, tipo="image/png", nome="c.png"):
    return client.post(f"/api/corsi/{corso.id}/copertina", headers=auth(utente), files={"file": (nome, dati, tipo)})


def test_la_formazione_carica_la_copertina_e_la_pagina_la_vede(client, auth, formazione, utente, crea_corso, db):
    c = crea_corso("Excel")
    assert client.get(f"/api/corsi/{c.id}", headers=auth(utente)).json()["copertina_url"] is None
    r = carica(client, auth, formazione, c, immagine())
    assert r.status_code == 200, r.text
    url = r.json()["copertina_url"]
    assert url.startswith(f"/api/corsi/{c.id}/copertina?t=") and "&v=" in url
    db.expire_all()
    assert os.path.isfile(db.get(Corso, c.id).copertina_path)
    # la vede ogni utente, con l'indirizzo firmato che riceve insieme al corso
    mia = client.get(f"/api/corsi/{c.id}", headers=auth(utente)).json()["copertina_url"]
    img = client.get(mia)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and "max-age" in img.headers["cache-control"]
    assert Image.open(io.BytesIO(img.content)).size == (1280, 720)
    # il file passa dalla stessa cifratura degli altri (attiva quando c'e' la chiave): letto con la funzione comune e' sempre un JPEG
    assert cifratura.leggi_file(db.get(Corso, c.id).copertina_path)[:3] == b"\xff\xd8\xff"


def test_l_immagine_si_porta_a_16_9_e_non_si_ingrandisce():
    larga = Image.open(io.BytesIO(svc.prepara(immagine(3000, 1000)))).size          # troppo larga: si ritaglia ai lati e si riduce
    alta = Image.open(io.BytesIO(svc.prepara(immagine(1000, 1600)))).size           # troppo alta: si ritaglia sopra e sotto; e' larga 1000, non si ingrandisce
    piccola = Image.open(io.BytesIO(svc.prepara(immagine(800, 500)))).size          # piu' piccola di 1280: si ritaglia, non si ingrandisce
    assert larga == (1280, 720) and alta == (1000, 562)
    assert piccola[0] == 800 and abs(piccola[0] / piccola[1] - 16 / 9) < 0.01


def test_le_trasparenze_diventano_bianche_e_le_foto_girate_si_raddrizzano():
    buf = io.BytesIO(); Image.new("RGBA", (1280, 720), (0, 0, 0, 0)).save(buf, "PNG")
    pixel = Image.open(io.BytesIO(svc.prepara(buf.getvalue()))).getpixel((10, 10))
    assert min(pixel) > 245                                                          # bianco, non nero
    esif = Image.Exif(); esif[274] = 6                                              # «ruotata di 90 gradi»
    buf = io.BytesIO(); Image.new("RGB", (1600, 900), (200, 30, 30)).save(buf, "JPEG", exif=esif)
    # raddrizzata diventa 900x1600 (alta): ritagliata a 16:9 resta 900 di larghezza. Se non si raddrizzasse sarebbe 1280x720.
    assert Image.open(io.BytesIO(svc.prepara(buf.getvalue()))).size == (900, 506)


@pytest.mark.parametrize("dati,tipo,atteso", [
    (b"non sono un'immagine", "image/png", "non è un'immagine valida"),
    (immagine(300, 200), "image/png", "troppo piccola"),
    (immagine(), "application/pdf", "Formato non supportato"),
    (b"\x00" * (5 * 1024 * 1024 + 10), "image/png", "troppo grande"),
])
def test_file_non_ammessi(client, auth, formazione, crea_corso, dati, tipo, atteso):
    c = crea_corso("Excel")
    r = carica(client, auth, formazione, c, dati, tipo)
    assert r.status_code == 400 and atteso in r.json()["detail"]
    assert client.get(f"/api/corsi/{c.id}", headers=auth(formazione)).json()["copertina_url"] is None


def test_solo_la_formazione_cambia_la_copertina(client, auth, utente, formazione, crea_corso):
    c = crea_corso("Excel")
    assert carica(client, auth, utente, c, immagine()).status_code == 403
    assert client.delete(f"/api/corsi/{c.id}/copertina", headers=auth(utente)).status_code == 403
    assert carica(client, auth, formazione, c, immagine()).status_code == 200
    assert client.delete(f"/api/corsi/{c.id}/copertina", headers=auth(utente)).status_code == 403


def test_sostituire_e_togliere(client, auth, formazione, utente, crea_corso, db):
    c = crea_corso("Excel")
    primo = carica(client, auth, formazione, c, immagine(colore=(200, 0, 0))).json()["copertina_url"]
    secondo = carica(client, auth, formazione, c, immagine(colore=(0, 0, 200))).json()["copertina_url"]
    assert primo.split("&v=")[1] != secondo.split("&v=")[1]                          # il codice cambia con l'immagine: nessuna vecchia in memoria
    db.expire_all(); percorso = db.get(Corso, c.id).copertina_path
    assert client.delete(f"/api/corsi/{c.id}/copertina", headers=auth(formazione)).status_code == 200
    db.expire_all()
    assert db.get(Corso, c.id).copertina_path is None and not os.path.exists(percorso)
    assert client.get(secondo).status_code == 404                                    # il link di prima non serve piu'


def test_gli_indirizzi_sono_firmati_e_stabili(client, auth, formazione, utente, crea_corso, crea_utente):
    c = crea_corso("Excel"); altro = crea_corso("Privacy")
    carica(client, auth, formazione, c, immagine()); carica(client, auth, formazione, altro, immagine())
    url = client.get(f"/api/corsi/{c.id}", headers=auth(utente)).json()["copertina_url"]
    assert client.get(f"/api/corsi/{c.id}", headers=auth(crea_utente("x@t.it"))).json()["copertina_url"] == url      # stesso indirizzo per tutti: il browser lo tiene in memoria
    assert client.get(f"/api/corsi/{c.id}/copertina").status_code == 422                                          # senza firma
    assert client.get(f"/api/corsi/{c.id}/copertina?t=falso").status_code == 401
    t = url.split("t=")[1].split("&")[0]
    assert client.get(f"/api/corsi/{altro.id}/copertina?t={t}").status_code == 401                                 # la firma e' di quel corso
    assert client.get(f"/api/corsi/{c.id}/copertina?t={t}").status_code == 200


def test_la_copertina_arriva_a_catalogo_home_e_pagina_del_corso(client, auth, formazione, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    from datetime import timedelta
    from conftest import adesso
    c = crea_corso("Excel"); c.permetti_autoiscrizione = True; db.commit()
    carica(client, auth, formazione, c, immagine())
    e = crea_edizione(c, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=5))
    crea_iscrizione(e, utente)
    atteso = client.get(f"/api/corsi/{c.id}", headers=auth(utente)).json()["copertina_url"]
    assert client.get("/api/catalogo", headers=auth(utente)).json()[0]["corso_copertina_url"] == atteso
    assert client.get("/api/edizioni/mie/iscrizioni", headers=auth(utente)).json()[0]["corso_copertina_url"] == atteso
    assert client.get(f"/api/edizioni/{e.id}", headers=auth(utente)).json()["corso_copertina_url"] == atteso


def test_eliminando_il_corso_va_via_anche_la_copertina(client, auth, admin, crea_corso, db):
    c = crea_corso("Per sbaglio")
    carica(client, auth, admin, c, immagine())
    db.expire_all(); percorso = db.get(Corso, c.id).copertina_path
    assert os.path.isfile(percorso)
    assert client.post(f"/api/corsi/{c.id}/elimina", headers=auth(admin), json={"conferma": "Per sbaglio"}).status_code == 200
    assert not os.path.exists(percorso)


def test_modificare_il_corso_non_tocca_la_copertina(client, auth, formazione, crea_corso):
    c = crea_corso("Excel")
    url = carica(client, auth, formazione, c, immagine()).json()["copertina_url"]
    r = client.put(f"/api/corsi/{c.id}", headers=auth(formazione), json={"titolo": "Excel base", "durata_minuti": 60})
    assert r.status_code == 200 and r.json()["copertina_url"] == url
