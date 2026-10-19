"""2.4.1: gestione dei video (proprieta', capitoli, sottotitoli, eliminazione) dalla pagina Video."""
import os

import pytest

from app.models.edizione import ModalitaErogazione
from app.models.video import StatoVideo, VideoCapitolo, VideoContenuto, VideoVersione


@pytest.fixture
def video(db, tmp_path):
    f, s, o, v1 = (tmp_path / n for n in ("v.mp4", "v.vtt", "orig.mp4", "v720.mp4"))
    for p in (f, s, o, v1):
        p.write_bytes(b"x" * 20)
    v = VideoContenuto(titolo="Sicurezza", file_path=str(f), sottotitoli_path=str(s), file_originale=str(o),
                       stato=StatoVideo.pronto, durata_secondi=120)
    db.add(v); db.flush()
    db.add(VideoVersione(video_id=v.id, altezza=720, file_path=str(v1)))
    db.commit(); db.refresh(v)
    return v


def test_l_elenco_dice_in_quante_sessioni_e_usato(client, auth, formazione, video, crea_corso, crea_edizione):
    assert client.get("/api/video", headers=auth(formazione)).json()[0]["usato_in"] == 0
    crea_edizione(crea_corso("A"), modalita=ModalitaErogazione.video, video_id=video.id)
    crea_edizione(crea_corso("B"), modalita=ModalitaErogazione.video, video_id=video.id)
    assert client.get("/api/video", headers=auth(formazione)).json()[0]["usato_in"] == 2
    assert client.get(f"/api/video/{video.id}", headers=auth(formazione)).json()["usato_in"] == 2


def test_il_titolo_si_cambia_ma_non_puo_essere_vuoto(client, auth, formazione, video):
    assert client.put(f"/api/video/{video.id}", headers=auth(formazione), json={"titolo": "  Nuovo titolo "}).status_code == 200
    assert client.get(f"/api/video/{video.id}", headers=auth(formazione)).json()["titolo"] == "Nuovo titolo"
    assert client.put(f"/api/video/{video.id}", headers=auth(formazione), json={"titolo": "   "}).status_code == 400


def test_capitoli_si_aggiungono_si_modificano_e_si_controllano(client, auth, formazione, video, db):
    r = client.post(f"/api/video/{video.id}/capitoli", headers=auth(formazione), json={"titolo": " Introduzione ", "inizio_secondi": 0})
    assert r.status_code == 200
    cid = r.json()["id"]
    assert client.put(f"/api/video/{video.id}/capitoli/{cid}", headers=auth(formazione), json={"titolo": "Apertura", "inizio_secondi": 30}).status_code == 200
    c = client.get(f"/api/video/{video.id}", headers=auth(formazione)).json()["capitoli"][0]
    assert (c["titolo"], c["inizio_secondi"]) == ("Apertura", 30)
    # controlli: titolo vuoto, tempo negativo, oltre la fine (120 s)
    for corpo in ({"titolo": " ", "inizio_secondi": 5}, {"titolo": "x", "inizio_secondi": -1}, {"titolo": "x", "inizio_secondi": 121}):
        assert client.post(f"/api/video/{video.id}/capitoli", headers=auth(formazione), json=corpo).status_code == 400
        assert client.put(f"/api/video/{video.id}/capitoli/{cid}", headers=auth(formazione), json=corpo).status_code == 400
    # un capitolo di un altro video non si tocca da questo
    assert client.put(f"/api/video/{video.id}/capitoli/00000000-0000-0000-0000-000000000000", headers=auth(formazione),
                      json={"titolo": "x", "inizio_secondi": 1}).status_code == 404
    assert client.delete(f"/api/video/{video.id}/capitoli/{cid}", headers=auth(formazione)).status_code == 200
    assert db.query(VideoCapitolo).count() == 0


def test_si_tolgono_i_sottotitoli(client, auth, formazione, video, db):
    percorso = video.sottotitoli_path
    assert os.path.exists(percorso)
    assert client.delete(f"/api/video/{video.id}/sottotitoli", headers=auth(formazione)).status_code == 200
    db.expire_all()
    assert db.get(VideoContenuto, video.id).sottotitoli_path is None and not os.path.exists(percorso)
    assert client.get(f"/api/video/{video.id}", headers=auth(formazione)).json()["ha_sottotitoli"] is False
    assert client.delete(f"/api/video/{video.id}/sottotitoli", headers=auth(formazione)).status_code == 200   # ripeterlo non da' errore


def test_un_video_usato_non_si_elimina_uno_libero_si_con_i_suoi_file(client, auth, formazione, video, db, crea_corso, crea_edizione):
    vid = video.id
    ed = crea_edizione(crea_corso(), modalita=ModalitaErogazione.video, video_id=vid)
    r = client.delete(f"/api/video/{vid}", headers=auth(formazione))
    assert r.status_code == 400 and "1 sessione" in r.json()["detail"]
    assert db.get(VideoContenuto, vid) is not None
    file_ = [video.file_path, video.sottotitoli_path, video.file_originale] + [x.file_path for x in video.versioni]
    ed.video_id = None; db.commit()                                         # scollegato dalla sessione
    assert client.delete(f"/api/video/{vid}", headers=auth(formazione)).status_code == 200
    db.expire_all()
    assert db.get(VideoContenuto, vid) is None
    assert not any(os.path.exists(p) for p in file_)                        # via anche i file (qualita', originale, sottotitoli)
    assert db.query(VideoVersione).count() == 0


def test_un_video_in_elaborazione_non_si_elimina(client, auth, formazione, db):
    v = VideoContenuto(titolo="In corso", stato=StatoVideo.in_elaborazione)
    db.add(v); db.commit()
    assert client.delete(f"/api/video/{v.id}", headers=auth(formazione)).status_code == 400


def test_solo_chi_gestisce_la_formazione_gestisce_i_video(client, auth, utente, video):
    for metodo, url, corpo in (("put", f"/api/video/{video.id}", {"titolo": "x"}), ("delete", f"/api/video/{video.id}", None),
                               ("delete", f"/api/video/{video.id}/sottotitoli", None)):
        r = getattr(client, metodo)(url, headers=auth(utente), **({"json": corpo} if corpo else {}))
        assert r.status_code == 403
