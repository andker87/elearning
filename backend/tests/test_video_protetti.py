"""Video protetti da indirizzi a tempo, CORS chiuso e upload a pezzi (1.9.0)."""
import io
from datetime import datetime, timedelta, timezone

import pytest
import jwt

from app.api import video as api_video
from app.config import settings
from app.models.edizione import ModalitaErogazione
from app.models.iscrizione import StatoIscrizione
from app.models.video import StatoVideo, VideoContenuto


@pytest.fixture
def video_pronto(db, tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"0123456789" * 100)
    s = tmp_path / "v.vtt"
    s.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nCiao\n")
    v = VideoContenuto(titolo="Sicurezza", file_path=str(f), sottotitoli_path=str(s), stato=StatoVideo.pronto, durata_secondi=60)
    db.add(v); db.commit(); db.refresh(v)
    return v


@pytest.fixture
def edizione_video(crea_corso, crea_edizione, video_pronto):
    return crea_edizione(crea_corso(), modalita=ModalitaErogazione.video, video_id=video_pronto.id,
                         data_inizio=datetime.now(timezone.utc) - timedelta(days=1))     # gia' iniziata: da quando inizia il video si apre


def test_cartella_pubblica_dei_video_non_esiste_piu(client):
    assert client.get("/videos/qualsiasi.mp4").status_code == 404


def test_senza_indirizzo_il_file_non_si_apre(client, video_pronto):
    assert client.get(f"/api/video/{video_pronto.id}/file").status_code == 422
    assert client.get(f"/api/video/{video_pronto.id}/file?t=falso").status_code == 401


def test_iscritto_ottiene_indirizzo_e_guarda_con_ripresa(client, auth, utente, video_pronto, edizione_video, crea_iscrizione):
    crea_iscrizione(edizione_video, utente)
    r = client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(utente))
    assert r.status_code == 200
    assert r.json()["sottotitoli"]
    f = client.get(r.json()["video"])
    assert f.status_code == 200 and len(f.content) == 1000
    assert f.headers["content-type"].startswith("video/mp4")
    assert "no-store" in f.headers["cache-control"]
    parte = client.get(r.json()["video"], headers={"Range": "bytes=0-9"})
    assert parte.status_code == 206 and parte.content == b"0123456789"
    assert client.get(r.json()["sottotitoli"]).text.startswith("WEBVTT")


@pytest.mark.parametrize("stato", [StatoIscrizione.annullato, StatoIscrizione.in_lista_attesa])
def test_non_iscritto_o_annullato_non_ottiene_indirizzo(client, auth, utente, video_pronto, edizione_video, crea_iscrizione, stato):
    assert client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(utente)).status_code == 404
    crea_iscrizione(edizione_video, utente, stato=stato)
    assert client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(utente)).status_code == 404
    assert client.get(f"/api/video/{video_pronto.id}", headers=auth(utente)).status_code == 404


def test_formazione_vede_tutto_e_senza_login_nulla(client, auth, formazione, video_pronto):
    assert client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(formazione)).status_code == 200
    assert client.get(f"/api/video/{video_pronto.id}/accesso").status_code in (401, 403)


def test_elenco_video_solo_per_la_formazione(client, auth, utente, formazione, video_pronto):
    assert client.get("/api/video", headers=auth(utente)).status_code == 403
    r = client.get("/api/video", headers=auth(formazione))
    assert r.status_code == 200 and "file_path" not in r.json()[0] and r.json()[0]["ha_file"] is True


def test_indirizzo_scaduto_o_di_altro_video_rifiutato(client, video_pronto, db):
    def tok(**kw):
        d = {"typ": "video", "vid": str(video_pronto.id), "k": "file", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        d.update(kw)
        return jwt.encode(d, settings.SECRET_KEY, algorithm="HS256")
    url = f"/api/video/{video_pronto.id}/file?t="
    assert client.get(url + tok()).status_code == 200
    assert client.get(url + tok(exp=datetime.now(timezone.utc) - timedelta(seconds=5))).status_code == 401
    assert client.get(url + tok(vid="00000000-0000-0000-0000-000000000000")).status_code == 401
    assert client.get(url + tok(k="sottotitoli")).status_code == 401   # un indirizzo per i sottotitoli non apre il video
    assert client.get(url + tok(typ="sessione")).status_code == 401
    # un normale token di sessione non vale come indirizzo del video
    assert client.get(url + jwt.encode({"sub": "x@test.it"}, settings.SECRET_KEY, algorithm="HS256")).status_code == 401


def test_cors_chiuso_di_default(client):
    r = client.get("/api/auth/me", headers={"Origin": "https://sito-esterno.example"})
    assert "access-control-allow-origin" not in r.headers
    r = client.options("/api/auth/me", headers={"Origin": "https://sito-esterno.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_ignora_asterisco_e_spazi(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", " https://a.example , * ,https://b.example,")
    assert settings.cors_origins_lista == ["https://a.example", "https://b.example"]
    monkeypatch.setattr(settings, "CORS_ORIGINS", None)
    assert settings.cors_origins_lista == []


def test_upload_si_ferma_oltre_il_limite_senza_lasciare_file(client, auth, formazione, monkeypatch, tmp_path):
    monkeypatch.setattr(api_video, "ORIGINALI_DIR", str(tmp_path))
    monkeypatch.setattr(api_video, "MAX_VIDEO_BYTES", 2 * 1024 * 1024)
    r = client.post("/api/video", headers=auth(formazione), data={"titolo": "Grande"},
                    files={"file": ("grande.mp4", io.BytesIO(b"x" * (3 * 1024 * 1024)), "video/mp4")})
    assert r.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_sottotitoli_oltre_limite_rifiutato(client, auth, formazione, video_pronto, monkeypatch, tmp_path):
    cartella = tmp_path / "sub"; cartella.mkdir()
    monkeypatch.setattr(api_video, "SOTTOTITOLI_DIR", str(cartella))
    monkeypatch.setattr(api_video, "MAX_SOTTOTITOLI_BYTES", 100)
    r = client.post(f"/api/video/{video_pronto.id}/sottotitoli", headers=auth(formazione),
                    files={"file": ("a.vtt", io.BytesIO(b"x" * 500), "text/vtt")})
    assert r.status_code == 413 and list(cartella.iterdir()) == []
    assert open(video_pronto.sottotitoli_path).read().startswith("WEBVTT")   # quello precedente resta


def test_indirizzo_valido_di_video_cancellato_da_404(client):
    vid = "00000000-0000-0000-0000-000000000000"
    tok = jwt.encode({"typ": "video", "vid": vid, "k": "file", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                     settings.SECRET_KEY, algorithm="HS256")
    assert client.get(f"/api/video/{vid}/file?t={tok}").status_code == 404


def test_un_docente_della_sessione_vede_il_video_e_ne_ha_l_accesso_chi_non_c_entra_no(client, db, auth, utente, crea_utente, edizione_video, video_pronto):
    from app.models.edizione import EdizioneDocente
    docente = crea_utente("docente@test.it", is_formatore=True)
    db.add(EdizioneDocente(edizione_id=edizione_video.id, user_id=docente.id)); db.commit()
    assert client.get(f"/api/video/{video_pronto.id}", headers=auth(docente)).status_code == 200          # per l'anteprima dalla pagina della sessione
    assert client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(docente)).status_code == 200
    estraneo = crea_utente("estraneo@test.it", is_formatore=True)                                          # docente, ma non di questa sessione
    assert client.get(f"/api/video/{video_pronto.id}", headers=auth(estraneo)).status_code == 404
    assert client.get(f"/api/video/{video_pronto.id}/accesso", headers=auth(utente)).status_code == 404   # e neanche chi non c'entra
