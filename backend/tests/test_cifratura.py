"""Cifratura a riposo (1.9.3): formato dei file, chiavi, avvio, conversione, integrazione con i file della piattaforma."""
import io
import os

import pytest
from PIL import Image

from app.config import settings
from app.models.azienda import Azienda
from app.services import cifratura as c
from app.services import cifratura_ops as ops


@pytest.fixture
def chiave(monkeypatch):
    k = c.genera_chiave()
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", k)
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)
    return k


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (10, 120, 100)).save(buf, format="PNG")
    return buf.getvalue()


# --- formato e chiavi ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [0, 1, 1000, c.BLOCCO - 1, c.BLOCCO, c.BLOCCO + 1, 3 * c.BLOCCO, 3 * c.BLOCCO + 17])
def test_scrittura_e_lettura_di_ogni_dimensione(chiave, tmp_path, n):
    dati = os.urandom(n)
    p = str(tmp_path / "f.bin")
    c.scrivi_file(p, dati)
    assert open(p, "rb").read(4) == c.MAGIC and (n < 32 or dati[:32] not in open(p, "rb").read())   # contenuto non leggibile nel file
    assert c.leggi_file(p) == dati and c.dimensione_in_chiaro(p) == n
    assert c.stato_file(p) == "cifrato"


def test_senza_chiave_il_file_resta_in_chiaro(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    p = str(tmp_path / "f.txt")
    c.scrivi_file(p, b"ciao")
    assert open(p, "rb").read() == b"ciao" and c.leggi_file(p) == b"ciao" and c.stato_file(p) == "chiaro"


def test_file_in_chiaro_si_legge_anche_con_la_chiave(chiave, tmp_path):
    p = tmp_path / "vecchio.txt"
    p.write_bytes(b"scritto prima della cifratura")
    assert c.leggi_file(str(p)) == b"scritto prima della cifratura"


def test_lettura_di_un_intervallo(chiave, tmp_path):
    dati = os.urandom(3 * c.BLOCCO + 500)
    p = str(tmp_path / "v.bin")
    c.scrivi_file(p, dati)
    for a, b in [(0, 9), (c.BLOCCO - 5, c.BLOCCO + 5), (c.BLOCCO, 2 * c.BLOCCO - 1), (2 * c.BLOCCO + 3, len(dati) - 1), (len(dati) - 1, len(dati) - 1)]:
        assert b"".join(c.scorri_intervallo(p, a, b)) == dati[a:b + 1]


def test_alterazione_e_troncamento_si_scoprono(chiave, tmp_path):
    dati = os.urandom(3 * c.BLOCCO)
    p = tmp_path / "f.bin"
    c.scrivi_file(str(p), dati)
    originale = p.read_bytes()
    alterato = bytearray(originale); alterato[100] ^= 1
    p.write_bytes(bytes(alterato))
    with pytest.raises(c.ContenutoNonValido):
        c.leggi_file(str(p))
    p.write_bytes(originale[:c.INTESTAZIONE + 2 * (c.BLOCCO + c.TAG)])   # tolto l'ultimo blocco
    with pytest.raises(c.ContenutoNonValido):
        c.leggi_file(str(p))


def test_chiave_sbagliata_o_mancante(chiave, tmp_path, monkeypatch):
    p = str(tmp_path / "f.bin")
    c.scrivi_file(p, b"segreto")
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    with pytest.raises(c.ChiaveMancante):
        c.leggi_file(p)
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    with pytest.raises(c.ChiaveMancante):
        c.leggi_file(p)


def test_cambio_chiave_con_la_precedente(chiave, tmp_path, monkeypatch):
    p = str(tmp_path / "f.bin")
    c.scrivi_file(p, b"dati importanti")
    vecchia = chiave
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", vecchia)
    assert c.leggi_file(p) == b"dati importanti" and c.stato_file(p) == "altra_chiave"
    assert ops.converti_file("ruota", [str(tmp_path)])["convertiti"] == 1
    assert c.stato_file(p) == "cifrato"
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)   # la vecchia non serve piu'
    assert c.leggi_file(p) == b"dati importanti"


def test_chiave_non_valida_rifiutata(monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", "troppo-corta")
    with pytest.raises(c.ErroreCifratura):
        c.cifra_testo("x")


def test_testi_cifrati(chiave):
    t = c.cifra_testo("-----BEGIN PRIVATE KEY-----")
    assert t.startswith("enc:v1:") and "BEGIN" not in t and c.decifra_testo(t) == "-----BEGIN PRIVATE KEY-----"
    assert c.cifra_testo(t) == t                       # non si cifra due volte
    assert c.decifra_testo("in chiaro") == "in chiaro" and c.cifra_testo(None) is None
    with pytest.raises(c.ContenutoNonValido):
        c.decifra_testo(t[:-4] + "AAAA")


def test_upload_a_pezzi_con_limite(chiave, tmp_path):
    import asyncio

    class Finto:
        def __init__(self, dati): self.b = io.BytesIO(dati)
        async def read(self, n): return self.b.read(n)
    p = str(tmp_path / "up.bin")
    dati = os.urandom(2_500_000)
    assert asyncio.run(c.salva_upload(Finto(dati), p, 3_000_000, lambda l: ValueError("troppo"))) == len(dati)
    assert c.leggi_file(p) == dati
    q = str(tmp_path / "grande.bin")
    with pytest.raises(ValueError):
        asyncio.run(c.salva_upload(Finto(dati), q, 1_000_000, lambda l: ValueError("troppo")))
    assert not os.path.exists(q) and [f for f in os.listdir(tmp_path) if f.endswith(".parte")] == []


# --- avvio ---------------------------------------------------------------------------------------

def test_avvio_senza_cifratura_non_fa_nulla(db):
    ops.controlla_avvio(db)
    assert db.query(Azienda).first().cifratura_verifica is None


def test_prima_attivazione_segna_la_cifratura_in_uso(db, chiave):
    ops.controlla_avvio(db)
    assert db.query(Azienda).first().cifratura_verifica.startswith("enc:v1:")
    ops.controlla_avvio(db)   # riavvio con la stessa chiave: nessun problema


def test_riavvio_senza_chiave_dopo_attivazione_si_ferma(db, chiave, monkeypatch):
    ops.controlla_avvio(db)
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    with pytest.raises(ops.ErroreAvvio, match="manca|non e' impostata"):
        ops.controlla_avvio(db)


def test_riavvio_con_chiave_sbagliata_si_ferma(db, chiave, monkeypatch):
    ops.controlla_avvio(db)
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    with pytest.raises(ops.ErroreAvvio, match="non corrisponde"):
        ops.controlla_avvio(db)


def test_cifratura_obbligatoria_senza_chiave_non_parte(db, monkeypatch):
    monkeypatch.setattr(settings, "CIFRATURA_OBBLIGATORIA", True)
    with pytest.raises(ops.ErroreAvvio, match="OBBLIGATORIA"):
        ops.controlla_avvio(db)


def test_cambio_chiave_completo_con_verifica(db, chiave, monkeypatch):
    ops.controlla_avvio(db)
    vecchia = chiave
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", vecchia)
    ops.controlla_avvio(db)                      # parte: la verifica si legge con la precedente
    ops.converti_db(db, "ruota")
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)
    ops.controlla_avvio(db)                      # ora basta la nuova


# --- conversione ---------------------------------------------------------------------------------

def test_cifra_e_decifra_le_cartelle_e_il_database(db, chiave, tmp_path):
    (tmp_path / "sotto").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF-uno")
    (tmp_path / "sotto" / "b.png").write_bytes(b"png-due")
    db.add(Azienda(vapid_private_key="PEM-PRIVATA")); db.commit()
    assert ops.riepilogo([str(tmp_path)])["chiaro"] == 2
    assert ops.converti_file("cifra", [str(tmp_path)])["convertiti"] == 2
    assert ops.riepilogo([str(tmp_path)]) == {"chiaro": 0, "cifrato": 2, "altra_chiave": 0, "illeggibili": 0}
    assert ops.converti_file("cifra", [str(tmp_path)])["convertiti"] == 0      # idempotente
    ops.converti_db(db, "cifra")
    assert db.query(Azienda).first().vapid_private_key.startswith("enc:v1:")
    assert ops.converti_file("decifra", [str(tmp_path)])["convertiti"] == 2
    assert (tmp_path / "a.pdf").read_bytes() == b"%PDF-uno"
    ops.converti_db(db, "decifra")
    assert db.query(Azienda).first().vapid_private_key == "PEM-PRIVATA"


def test_un_file_rotto_non_ferma_la_conversione(db, chiave, tmp_path):
    (tmp_path / "ok.txt").write_bytes(b"ok")
    c.scrivi_file(str(tmp_path / "rotto.bin"), b"x" * 10)
    dati = bytearray((tmp_path / "rotto.bin").read_bytes()); dati[-1] ^= 1
    (tmp_path / "rotto.bin").write_bytes(bytes(dati))
    r = ops.converti_file("decifra", [str(tmp_path)])
    assert len(r["errori"]) == 1 and "rotto.bin" in r["errori"][0]


def test_disattivazione_solo_se_non_resta_nulla_di_cifrato(db, chiave, tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "CARTELLE", [str(tmp_path)])
    ops.controlla_avvio(db)
    c.scrivi_file(str(tmp_path / "x.bin"), b"dati")
    with pytest.raises(ops.ErroreAvvio):
        ops.disattiva(db)
    ops.converti_file("decifra", [str(tmp_path)])
    ops.disattiva(db)
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    ops.controlla_avvio(db)                      # ora riparte senza chiave


# --- integrazione con la piattaforma --------------------------------------------------------------

def test_logo_cifrato_su_disco_e_pubblico_decifrato(client, auth, admin, chiave):
    r = client.post("/api/azienda/logo", headers=auth(admin), files={"file": ("logo.png", _png(), "image/png")})
    assert r.status_code == 200
    percorso = "/app/uploads/azienda/logo.png"
    assert open(percorso, "rb").read(4) == c.MAGIC               # su disco e' cifrato
    pubblico = client.get("/uploads/azienda/logo.png")           # senza login, come la pagina di accesso
    assert pubblico.status_code == 200 and pubblico.content == _png() and pubblico.headers["content-type"] == "image/png"
    assert client.get("/api/azienda/icona?size=64").status_code == 200   # l'icona dell'app si ricava dal logo cifrato
    os.remove(percorso)


def test_template_attestato_con_immagine_cifrata_genera_pdf(client, auth, formazione, chiave):
    t = client.post("/api/certificato-templates", headers=auth(formazione), json={"nome": "T", "campi": []}).json()
    r = client.post(f"/api/certificato-templates/{t['id']}/immagine", headers=auth(formazione), files={"file": ("s.png", _png(), "image/png")})
    assert r.status_code == 200
    percorso = f"/app/uploads/template_attestati/{t['id']}.png"
    assert open(percorso, "rb").read(4) == c.MAGIC
    assert client.get(f"/api/certificato-templates/{t['id']}/immagine", headers=auth(formazione)).content == _png()
    anteprima = client.get(f"/api/certificato-templates/{t['id']}/anteprima.pdf", headers=auth(formazione))
    assert anteprima.status_code == 200 and anteprima.content.startswith(b"%PDF")


def test_informativa_pdf_cifrata(client, auth, admin, utente, chiave):
    pdf = b"%PDF-1.4 informativa di prova"
    assert client.post("/api/privacy/informativa/pdf", headers=auth(admin), files={"file": ("i.pdf", pdf, "application/pdf")}).status_code == 200
    assert open("/app/uploads/azienda/informativa-privacy.pdf", "rb").read(4) == c.MAGIC
    r = client.get("/api/privacy/informativa.pdf", headers=auth(utente))
    assert r.status_code == 200 and r.content == pdf
    client.delete("/api/privacy/informativa/pdf", headers=auth(admin))


def test_attestato_emesso_cifrato_e_scaricabile(client, auth, db, utente, formazione, crea_corso, crea_edizione, crea_iscrizione, chiave):
    from app.models.certificato import Certificato
    from app.services import certificati
    corso = crea_corso(); ed = crea_edizione(corso); isc = crea_iscrizione(ed, utente)
    percorso = f"{certificati.CERT_DIR}/prova-cifrato.pdf"
    certificati.genera_pdf(percorso, nome_discente="Mario Rossi", titolo_corso="Corso", data_evento="01/01/2026", codice_verifica="ABC")
    assert open(percorso, "rb").read(4) == c.MAGIC
    cert = Certificato(iscrizione_id=isc.id, codice_verifica="ABC", pdf_path=percorso)
    db.add(cert); db.commit()
    r = client.get(f"/api/certificati/{cert.id}/pdf", headers=auth(utente))
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["cache-control"] == "private, no-store"
    assert client.get(f"/api/certificati/{cert.id}/pdf", headers=auth(formazione)).status_code == 200
    os.remove(percorso)


def test_chiave_sbagliata_da_503_non_500(client, auth, admin, chiave, monkeypatch):
    client.post("/api/azienda/logo", headers=auth(admin), files={"file": ("logo.png", _png(), "image/png")})
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    r = client.get("/uploads/azienda/logo.png")
    assert r.status_code == 503 and "CHIAVE_CIFRATURA" in r.json()["detail"]
    os.remove("/app/uploads/azienda/logo.png")


def test_stato_cifratura_nella_salute_e_nelle_info(client, auth, admin, utente, chiave):
    s = client.get("/api/admin/salute", headers=auth(admin)).json()["cifratura"]
    assert s["chiave_presente"] is True and "chiaro" in s["file"]
    assert client.get("/api/about", headers=auth(admin)).json()["cifratura"]["chiave_presente"] is True
    assert "cifratura" not in client.get("/api/about", headers=auth(utente)).json()


# --- token del calendario ---------------------------------------------------------------------------

def test_token_calendario_si_vede_una_volta_e_non_e_nel_database(client, auth, db, utente):
    assert client.get("/api/calendario/url", headers=auth(utente)).json() == {"attivo": False}
    r1 = client.post("/api/calendario/url/rigenera", headers=auth(utente)).json()
    token = r1["url"].split("token=")[1]
    db.refresh(utente)
    assert utente.calendar_token_hash and token not in utente.calendar_token_hash
    assert client.get("/api/calendario/url", headers=auth(utente)).json() == {"attivo": True}     # il link non si rivede
    assert client.get(f"/api/calendario/feed.ics?token={token}").status_code == 200
    r2 = client.post("/api/calendario/url/rigenera", headers=auth(utente)).json()
    assert client.get(f"/api/calendario/feed.ics?token={token}").status_code == 404                # il vecchio non vale piu'
    assert client.get(r2["url"]).status_code == 200


def test_allegato_esterno_cifrato_e_pacchetto_ispezione_in_chiaro(client, auth, db, formazione, crea_utente, crea_corso, crea_edizione, crea_iscrizione, chiave):
    import zipfile
    from app.models.evidenza import Evidenza
    from app.models.iscrizione import StatoIscrizione as S
    e = crea_edizione(crea_corso("C"))
    i = crea_iscrizione(e, crea_utente("p@test.it", full_name="Paola Neri"), S.completato, giorni_fa=3)
    r = client.post(f"/api/edizioni/{e.id}/evidenze/{i.id}/upload", headers=auth(formazione),
                    files={"file": ("att.pdf", b"%PDF-1.4 attestato esterno", "application/pdf")})
    assert r.status_code == 200, r.text
    ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id).first()
    assert open(ev.file_allegato_path, "rb").read(4) == c.MAGIC
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione)).content))
    contenuti = [z.read(n) for n in z.namelist() if n.startswith(tuple(x for x in z.namelist())) and "attestati_esterni" in n]
    assert contenuti == [b"%PDF-1.4 attestato esterno"]       # nello ZIP il documento e' leggibile
    os.remove(ev.file_allegato_path)


def test_allegato_troppo_grande_rifiutato(client, auth, formazione, crea_utente, crea_corso, crea_edizione, crea_iscrizione, monkeypatch):
    from app.api import evidenze
    monkeypatch.setattr(evidenze, "MAX_ALLEGATO_BYTES", 100)
    e = crea_edizione(crea_corso("C"))
    i = crea_iscrizione(e, crea_utente("q@test.it"))
    r = client.post(f"/api/edizioni/{e.id}/evidenze/{i.id}/upload", headers=auth(formazione), files={"file": ("a.pdf", b"x" * 500, "application/pdf")})
    assert r.status_code == 413


def test_strumento_da_riga_di_comando(db, chiave, tmp_path, monkeypatch, capsys):
    from app import cifratura_cli
    monkeypatch.setattr(ops, "CARTELLE", [str(tmp_path)])
    (tmp_path / "a.txt").write_bytes(b"uno")
    assert cifratura_cli.main(["genera-chiave"]) == 0 and len(capsys.readouterr().out.strip()) >= 43
    assert cifratura_cli.main(["cifra"]) == 0 and c.stato_file(str(tmp_path / "a.txt")) == "cifrato"
    assert cifratura_cli.main(["stato"]) == 0 and '"cifrato": 1' in capsys.readouterr().out
    assert cifratura_cli.main(["decifra"]) == 0 and c.stato_file(str(tmp_path / "a.txt")) == "chiaro"
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    assert cifratura_cli.main(["cifra"]) == 2


@pytest.mark.parametrize("n", [0, 5, c.BLOCCO, 2 * c.BLOCCO + 9])
def test_lettura_a_blocchi_uguale_alla_lettura_intera(chiave, tmp_path, n):
    dati = os.urandom(n)
    cifrato, chiaro = str(tmp_path / "c.bin"), str(tmp_path / "p.bin")
    c.scrivi_file(cifrato, dati)
    c.scrivi_file(chiaro, dati, cifra=False)
    assert b"".join(c.leggi_a_blocchi(cifrato)) == dati == b"".join(c.leggi_a_blocchi(chiaro))
    assert max((len(x) for x in c.leggi_a_blocchi(cifrato)), default=0) <= c.BLOCCO


def test_la_conversione_include_i_video_ma_non_i_file_temporanei():
    assert "/app/videos" in ops.CARTELLE and "/lavoro/" in ops.ESCLUSI and "/originali/" in ops.ESCLUSI


def test_il_link_del_calendario_non_finisce_in_cache(client, auth, utente):
    r = client.post("/api/calendario/url/rigenera", headers=auth(utente))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and "token=" in r.json()["url"]


def test_attestato_non_viene_emesso_incompleto_se_la_chiave_manca(chiave, tmp_path, monkeypatch):
    """Con il logo cifrato e la chiave sbagliata l'emissione deve fallire, non produrre un attestato senza logo."""
    from app.services import certificati
    logo = tmp_path / "logo.png"
    c.scrivi_file(str(logo), _png())
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    with pytest.raises(c.ChiaveMancante):
        certificati.genera_pdf(str(tmp_path / "a.pdf"), nome_discente="Mario", titolo_corso="C", data_evento="01/01/2026",
                               codice_verifica="X", logo_path=str(logo))
