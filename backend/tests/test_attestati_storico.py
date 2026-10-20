"""2.7.3: nome parlante dell'attestato e storico con le informazioni per riconoscerlo."""
import os
from datetime import datetime, timezone

from app.models.certificato import Certificato
from app.models.edizione import StatoEdizione as SE
from app.models.iscrizione import StatoIscrizione as S
from app.services.certificati import nome_file_attestato


def test_il_nome_del_file_e_parlante_e_sicuro():
    d = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)
    assert nome_file_attestato("Primo soccorso", "Rossi", "Mario", d) == "Primo-soccorso_Rossi_Mario_2026-10-21.pdf"
    # accenti, apostrofi, barre e simboli non sporcano il nome; i cognomi doppi restano leggibili
    assert nome_file_attestato("Sicurezza: rischio «alto» / D.Lgs. 81", "De Luca", "Maria Grazia", d) == "Sicurezza-rischio-alto-D-Lgs-81_De-Luca_Maria-Grazia_2026-10-21.pdf"
    assert nome_file_attestato("Qualità e perché", "D'Angelo", "Zoë", d) == "Qualita-e-perche_D-Angelo_Zoe_2026-10-21.pdf"
    assert nome_file_attestato("../../etc/passwd", "Rossi", "Mario", d).startswith("etc-passwd_")        # niente percorsi
    lungo = nome_file_attestato("x" * 300, "Rossi", "Mario", d)
    assert len(lungo) < 90 and lungo.endswith("_Rossi_Mario_2026-10-21.pdf")
    assert nome_file_attestato("", "", "", None) == "attestato.pdf"                                       # mai un nome vuoto


def test_storico_e_download_dell_attestato(client, auth, utente, formazione, crea_utente, db, crea_corso, crea_edizione, crea_iscrizione, tmp_path):
    from app.services import cifratura
    c = crea_corso("Antincendio"); c.durata_minuti = 150; db.commit()
    e = crea_edizione(c, stato=SE.chiusa); e.durata_minuti = 150; db.commit()      # alla chiusura la durata si congela sulla sessione
    i = crea_iscrizione(e, utente, stato=S.completato)
    pdf = tmp_path / "a.pdf"; cifratura.scrivi_file(str(pdf), b"%PDF-1.4 prova")
    cert = Certificato(iscrizione_id=i.id, codice_verifica="AB12CD34", pdf_path=str(pdf)); db.add(cert); db.commit(); db.refresh(cert)
    mie = client.get("/api/certificati/mie", headers=auth(utente)).json()
    assert len(mie) == 1
    r = mie[0]
    assert (r["corso_titolo"], r["modalita"], r["durata_minuti"], r["codice_verifica"]) == ("Antincendio", "esterna", 150, "AB12CD34")
    assert r["iscrizione_id"] == str(i.id)
    atteso = nome_file_attestato("Antincendio", utente.cognome, utente.nome, cert.emesso_at)
    assert r["nome_file"] == atteso and atteso.startswith("Antincendio_") and atteso.endswith(f"_{cert.emesso_at:%Y-%m-%d}.pdf")
    # nello storico la durata c'e' anche senza attestato
    iscr = client.get("/api/edizioni/mie/iscrizioni", headers=auth(utente)).json()
    assert iscr[0]["durata_effettiva_minuti"] == 150
    # il download usa lo stesso nome; con inline si apre nel browser
    scarica = client.get(f"/api/certificati/{cert.id}/pdf", headers=auth(utente))
    assert scarica.status_code == 200 and scarica.headers["content-disposition"] == f'attachment; filename="{r["nome_file"]}"'
    vista = client.get(f"/api/certificati/{cert.id}/pdf?inline=true", headers=auth(utente))
    assert vista.headers["content-disposition"].startswith("inline;")
    # il nome e' quello di chi ha ottenuto l'attestato, anche se lo scarica la Formazione
    assert client.get(f"/api/certificati/{cert.id}/pdf", headers=auth(formazione)).headers["content-disposition"] == scarica.headers["content-disposition"]
    assert client.get(f"/api/certificati/{cert.id}/pdf", headers=auth(crea_utente("altro@t.it"))).status_code == 403
