import secrets, os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from ..models.certificato import Certificato, TipoCertificato

CERT_DIR = "/app/uploads/certificati"

def genera_codice_verifica() -> str:
    return secrets.token_hex(8).upper()

def genera_pdf(path: str, *, nome_discente: str, titolo_corso: str,
               data_evento: str, codice_verifica: str, azienda: str = ""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 120, "Attestato di partecipazione")
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 180, azienda or "")
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 240, f"Si attesta che {nome_discente}")
    c.drawCentredString(width / 2, height - 265, f"ha partecipato al corso \"{titolo_corso}\"")
    c.drawCentredString(width / 2, height - 290, f"in data {data_evento}")
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 80, f"Codice di verifica: {codice_verifica}")
    c.drawCentredString(width / 2, 65, "Verificabile su richiesta presso l'ufficio formazione")
    c.showPage()
    c.save()

def crea_certificato(db, iscrizione, corso_titolo: str, nome_discente: str, azienda: str = "") -> Certificato:
    codice = genera_codice_verifica()
    filename = f"{iscrizione.id}_{codice}.pdf"
    path = os.path.join(CERT_DIR, filename)
    genera_pdf(path, nome_discente=nome_discente, titolo_corso=corso_titolo,
               data_evento=datetime.utcnow().strftime("%d/%m/%Y"),
               codice_verifica=codice, azienda=azienda)
    cert = Certificato(
        iscrizione_id=iscrizione.id,
        tipo=TipoCertificato.base,
        codice_verifica=codice,
        pdf_path=path,
    )
    db.add(cert)
    db.flush()
    return cert
