"""Video (1.9.4): piu' qualita', cifratura su disco, riproduzione a intervalli, originale eliminato."""
import os
from datetime import datetime, timedelta, timezone
import subprocess

import pytest

from app.config import settings
from app.models.edizione import ModalitaErogazione
from app.models.iscrizione import StatoIscrizione
from app.models.video import StatoVideo, VideoContenuto, VideoVersione
from app.services import cifratura as c
from app.services import video_elaborazione as ve


def _crea_sorgente(percorso, altezza=720, secondi=1):
    larghezza = altezza * 16 // 9 // 2 * 2
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={larghezza}x{altezza}:rate=10:duration={secondi}",
                    "-f", "lavfi", "-i", f"sine=duration={secondi}", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(percorso)], check=True, capture_output=True)


@pytest.fixture
def cartelle(tmp_path, monkeypatch):
    monkeypatch.setattr(ve, "PRONTI_DIR", str(tmp_path / "pronti"))
    monkeypatch.setattr(ve, "LAVORO_DIR", str(tmp_path / "lavoro"))
    return tmp_path


@pytest.fixture
def chiave(monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)


def _video_caricato(db, originale):
    v = VideoContenuto(titolo="Prova", file_originale=str(originale), stato=StatoVideo.caricato)
    db.add(v); db.commit(); db.refresh(v)
    return v


# --- scelta delle qualita' ------------------------------------------------------------------------

@pytest.mark.parametrize("origine, attese", [(2160, [480, 720, 1080, 2160]), (1440, [480, 720, 1080]), (1080, [480, 720, 1080]),
                                              (720, [480, 720]), (500, [480]), (360, [360]), (361, [360])])
def test_qualita_prodotte_mai_oltre_l_originale(origine, attese):
    assert ve.altezze_da_produrre(origine) == attese


def test_qualita_configurabili_da_ambiente(monkeypatch):
    monkeypatch.setattr(settings, "VIDEO_ALTEZZE", "720, 1080, 999, abc")
    assert ve.altezze_configurate() == [720, 1080]
    assert ve.altezze_da_produrre(2160) == [720, 1080]
    monkeypatch.setattr(settings, "VIDEO_ALTEZZE", "")
    assert ve.altezze_configurate() == [480, 720, 1080, 2160]


# --- conversione ----------------------------------------------------------------------------------

def test_conversione_cifrata_con_originale_eliminato(db, cartelle, chiave):
    originale = cartelle / "orig.mp4"
    _crea_sorgente(originale, 720)
    v = _video_caricato(db, originale)
    ve.transcodifica(str(v.id), str(originale))
    db.expire_all()
    v = db.get(VideoContenuto, v.id)
    assert v.stato == StatoVideo.pronto and v.altre_versioni_in_corso is False and v.durata_secondi == 1
    assert sorted(x.altezza for x in v.versioni) == [480, 720]
    assert v.file_path.endswith("_720p.mp4")                       # la predefinita e' la piu' vicina a 720p
    for x in v.versioni:
        assert open(x.file_path, "rb").read(4) == c.MAGIC          # cifrati su disco
        assert x.bitrate_kbps and x.dimensione_bytes
    assert not originale.exists() and v.file_originale is None     # originale eliminato
    assert not (cartelle / "lavoro" / str(v.id)).exists()          # nessun file temporaneo


def test_file_non_video_va_in_errore_e_non_lascia_nulla(db, cartelle, chiave):
    originale = cartelle / "testo.mp4"
    originale.write_text("non sono un video")
    v = _video_caricato(db, originale)
    ve.transcodifica(str(v.id), str(originale))
    db.expire_all()
    v = db.get(VideoContenuto, v.id)
    assert v.stato == StatoVideo.errore and not v.versioni and not originale.exists()


def test_riavvio_a_meta_conversione_recupera_e_ripulisce(db, cartelle):
    originale = cartelle / "sospeso.mp4"
    originale.write_bytes(b"in chiaro")
    v = _video_caricato(db, originale)
    v.stato = StatoVideo.in_elaborazione; v.altre_versioni_in_corso = True; db.commit()
    assert ve.recupera_interrotti(db) >= 1
    db.refresh(v)
    assert v.stato == StatoVideo.errore and not originale.exists() and v.file_originale is None and v.altre_versioni_in_corso is False


# --- riproduzione ---------------------------------------------------------------------------------

@pytest.fixture
def video_con_qualita(db, cartelle, chiave, crea_corso, crea_edizione):
    originale = cartelle / "orig.mp4"
    _crea_sorgente(originale, 720)
    v = _video_caricato(db, originale)
    ve.transcodifica(str(v.id), str(originale))
    db.expire_all()
    v = db.get(VideoContenuto, v.id)
    ed = crea_edizione(crea_corso(), modalita=ModalitaErogazione.video, video_id=v.id,
                       data_inizio=datetime.now(timezone.utc) - timedelta(days=1))     # gia' iniziata: da quando inizia il video si apre
    return v, ed


def test_accesso_elenca_le_qualita_e_ognuna_si_guarda(client, auth, utente, video_con_qualita, crea_iscrizione):
    v, ed = video_con_qualita
    crea_iscrizione(ed, utente)
    r = client.get(f"/api/video/{v.id}/accesso", headers=auth(utente)).json()
    assert [x["altezza"] for x in r["versioni"]] == [480, 720] and "/file/720?" in r["video"]
    for x in r["versioni"]:
        f = client.get(x["url"])
        assert f.status_code == 200 and f.content[4:8] == b"ftyp"          # arriva un MP4 in chiaro, decifrato al volo
        assert int(f.headers["content-length"]) == len(f.content)


def test_intervalli_come_li_chiede_un_player(client, auth, utente, video_con_qualita, crea_iscrizione):
    v, ed = video_con_qualita
    crea_iscrizione(ed, utente)
    url = client.get(f"/api/video/{v.id}/accesso", headers=auth(utente)).json()["video"]
    intero = client.get(url).content
    totale = len(intero)
    p = client.get(url, headers={"Range": "bytes=100-199"})
    assert p.status_code == 206 and p.content == intero[100:200] and p.headers["content-range"] == f"bytes 100-199/{totale}"
    assert client.get(url, headers={"Range": "bytes=500-"}).content == intero[500:]
    assert client.get(url, headers={"Range": "bytes=-50"}).content == intero[-50:]
    assert client.get(url, headers={"Range": f"bytes={totale - 10}-{totale + 9999}"}).content == intero[-10:]   # fine oltre il file
    assert client.get(url, headers={"Range": f"bytes={totale}-"}).status_code == 416
    assert client.get(url, headers={"Range": "bytes=abc"}).content == intero                                     # richiesta incomprensibile: tutto il file
    assert client.get(url, headers={"Range": "bytes=0-5,10-20"}).content == intero


def test_un_indirizzo_non_apre_un_altra_qualita(client, auth, utente, video_con_qualita, crea_iscrizione):
    v, ed = video_con_qualita
    crea_iscrizione(ed, utente)
    r = client.get(f"/api/video/{v.id}/accesso", headers=auth(utente)).json()
    url_720 = next(x["url"] for x in r["versioni"] if x["altezza"] == 720)
    assert client.get(url_720.replace("/file/720", "/file/480")).status_code == 401
    assert client.get(url_720.replace("/file/720", "/file/2160")).status_code == 401


def test_sottotitoli_cifrati_su_disco_e_letti_in_chiaro(client, auth, formazione, utente, db, video_con_qualita, crea_iscrizione, monkeypatch, tmp_path):
    from app.api import video as api_video
    v, ed = video_con_qualita
    cartella = tmp_path / "sub"; cartella.mkdir()
    monkeypatch.setattr(api_video, "SOTTOTITOLI_DIR", str(cartella))
    r = client.post(f"/api/video/{v.id}/sottotitoli", headers=auth(formazione), files={"file": ("s.vtt", b"WEBVTT\n\n00:00.000 --> 00:01.000\nCiao\n", "text/vtt")})
    assert r.status_code == 200
    db.expire_all(); v = db.get(VideoContenuto, v.id)
    assert open(v.sottotitoli_path, "rb").read(4) == c.MAGIC
    crea_iscrizione(ed, utente)
    acc = client.get(f"/api/video/{v.id}/accesso", headers=auth(utente)).json()
    assert client.get(acc["sottotitoli"]).text.startswith("WEBVTT")


def test_serializzazione_mostra_qualita_e_non_i_percorsi(client, auth, formazione, video_con_qualita):
    v, _ = video_con_qualita
    d = client.get("/api/video", headers=auth(formazione)).json()[0]
    assert d["qualita"] == [480, 720] and d["altre_qualita_in_preparazione"] is False
    assert not any("/app/" in str(x) or "pronti" in str(x) for x in d.values())


# --- conversione dei file esistenti -----------------------------------------------------------------

def test_lo_strumento_cifra_i_video_ma_non_i_file_di_lavoro(tmp_path, chiave):
    from app.services import cifratura_ops as ops
    (tmp_path / "pronti").mkdir(); (tmp_path / "lavoro" / "x").mkdir(parents=True); (tmp_path / "originali").mkdir()
    for f in ("pronti/a.mp4", "lavoro/x/480.mp4", "originali/o.mp4"):
        (tmp_path / f).write_bytes(b"dati")
    assert ops.converti_file("cifra", [str(tmp_path)])["convertiti"] == 1
    assert c.stato_file(str(tmp_path / "pronti/a.mp4")) == "cifrato"
    assert c.stato_file(str(tmp_path / "lavoro/x/480.mp4")) == "chiaro" and c.stato_file(str(tmp_path / "originali/o.mp4")) == "chiaro"
    assert any("videos" in x for x in ops.CARTELLE)


# --- scelta automatica lato server dei dati per il player (contratto) -----------------------------------

def test_predefinita_vicina_a_720():
    v = lambda h: VideoVersione(altezza=h, file_path=f"{h}")
    assert ve._predefinita([v(480), v(1080), v(2160)]).altezza == 480       # 480 dista 240, 1080 dista 360
    assert ve._predefinita([v(480), v(720), v(1080)]).altezza == 720
    assert ve._predefinita([v(1080), v(2160)]).altezza == 1080


def test_il_file_decifrato_e_un_video_valido_alla_qualita_dichiarata(client, auth, utente, video_con_qualita, crea_iscrizione, tmp_path):
    v, ed = video_con_qualita
    crea_iscrizione(ed, utente)
    r = client.get(f"/api/video/{v.id}/accesso", headers=auth(utente)).json()
    for x in r["versioni"]:
        f = tmp_path / f"{x['altezza']}.mp4"
        f.write_bytes(client.get(x["url"]).content)
        larghezza, altezza, durata = ve.sonda(str(f))
        assert altezza == x["altezza"] and 0.5 < durata < 2


def test_elenco_video_non_fa_una_query_per_video(client, auth, formazione, db):
    from sqlalchemy import event
    from app.database import engine
    for n in range(6):
        v = VideoContenuto(titolo=f"V{n}", file_path=f"/x/{n}.mp4", stato=StatoVideo.pronto)
        db.add(v); db.flush()
        db.add(VideoVersione(video_id=v.id, altezza=480, file_path=f"/x/{n}_480.mp4"))
        db.add(VideoVersione(video_id=v.id, altezza=720, file_path=f"/x/{n}_720.mp4"))
    db.commit()
    conta = []
    def registra(conn, cursor, statement, *resto):
        conta.append(statement)
    event.listen(engine, "before_cursor_execute", registra)
    try:
        r = client.get("/api/video", headers=auth(formazione))
    finally:
        event.remove(engine, "before_cursor_execute", registra)
    assert r.status_code == 200 and len(r.json()) == 6 and all(x["qualita"] == [480, 720] for x in r.json())
    selezioni_video = [q for q in conta if "FROM video_versioni" in q]
    assert len(selezioni_video) == 1          # una sola query per tutte le qualita', non una per video
