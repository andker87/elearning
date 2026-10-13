"""Pacchetto per l'ispezione: contenuto dello ZIP e perimetro."""
import csv
import io
import zipfile

from app.models.audit import AuditLog
from app.models.certificato import Certificato
from app.models.evidenza import Evidenza, FonteEvidenza
from app.models.iscrizione import StatoIscrizione as S


def apri(risposta):
    assert risposta.status_code == 200 and risposta.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(risposta.content))
    return z, {n.split("/", 1)[1]: n for n in z.namelist()}


def scenario(db, tmp_path, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = crea_corso("Sicurezza", validita_mesi=12)
    ed = crea_edizione(corso)
    a, b = crea_utente("a@test.it", full_name="Anna Bianchi"), crea_utente("b@test.it", full_name="Bruno Verdi")
    isc_a = crea_iscrizione(ed, a, S.completato, giorni_fa=10)
    isc_b = crea_iscrizione(ed, b, S.completato, giorni_fa=20)
    pdf = tmp_path / "att.pdf"
    pdf.write_bytes(b"%PDF-1.4 attestato")
    db.add(Certificato(iscrizione_id=isc_a.id, codice_verifica="CODICE123", pdf_path=str(pdf)))
    esterno = tmp_path / "ext.pdf"
    esterno.write_bytes(b"%PDF-1.4 esterno")
    db.add(Evidenza(iscrizione_id=isc_b.id, fonte=FonteEvidenza.upload_manuale, file_allegato_path=str(esterno)))
    db.commit()
    return a, b


def test_contenuto_del_pacchetto(client, db, tmp_path, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    scenario(db, tmp_path, crea_utente, crea_corso, crea_edizione, crea_iscrizione)
    z, nomi = apri(client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione)))
    assert {"LEGGIMI.txt", "registro_formazione.xlsx", "registro_formazione.pdf", "matrice_formativa.xlsx", "indice_documenti.csv"} <= set(nomi)
    assert any(n.startswith("attestati/Anna_Bianchi/") and n.endswith("CODICE123.pdf") for n in nomi)
    assert any(n.startswith("attestati_esterni/Bruno_Verdi/") for n in nomi)
    indice = list(csv.reader(io.StringIO(z.read(nomi["indice_documenti.csv"]).decode("utf-8-sig"))))
    assert len(indice) == 3 and {r[4] for r in indice[1:]} == {"CODICE123", ""}
    assert db.query(AuditLog).filter(AuditLog.action == "PACCHETTO_ISPEZIONE").count() == 1


def test_perimetro_per_persona(client, db, tmp_path, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    a, _ = scenario(db, tmp_path, crea_utente, crea_corso, crea_edizione, crea_iscrizione)
    z, nomi = apri(client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione), params={"user_id": str(a.id)}))
    assert "matrice_formativa.xlsx" not in nomi  # la matrice ha senso per gruppi di persone
    assert any("Anna_Bianchi" in n for n in nomi) and not any("Bruno_Verdi" in n for n in nomi)


def test_persona_inesistente(client, formazione, auth):
    assert client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione), params={"user_id": "00000000-0000-0000-0000-000000000000"}).status_code == 404


def test_file_mancanti_sul_disco_non_rompono_il_pacchetto(client, db, tmp_path, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    scenario(db, tmp_path, crea_utente, crea_corso, crea_edizione, crea_iscrizione)
    for f in tmp_path.iterdir():
        f.unlink()
    z, nomi = apri(client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione)))
    assert not any(n.startswith("attestati") for n in nomi)
