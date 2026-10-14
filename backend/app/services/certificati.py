import secrets, os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from ..models.certificato import Certificato, TipoCertificato
from ..models.azienda import Azienda
from ..models.edizione import EdizioneDocente, RuoloDocente
from ..models.user import User

CERT_DIR = "/app/uploads/certificati"

# Vocabolario fisso delle variabili disponibili nell'editor di template
# attestati (api/certificato_templates.py) e nella loro risoluzione qui sotto.
CAMPI_DISPONIBILI = [
    {"chiave": "nome_discente", "etichetta": "Nome partecipante"},
    {"chiave": "titolo_corso", "etichetta": "Titolo corso"},
    {"chiave": "data_evento", "etichetta": "Data"},
    {"chiave": "ore_corso", "etichetta": "Monte ore"},
    {"chiave": "azienda_nome", "etichetta": "Azienda"},
    {"chiave": "ente_erogatore", "etichetta": "Ente erogatore (corsi esterni)"},
    {"chiave": "docente_nome", "etichetta": "Docente(i)"},
    {"chiave": "codice_verifica", "etichetta": "Codice di verifica"},
]

def azienda_info(db):
    """Ragione sociale e logo da mostrare sull'attestato, se impostati."""
    a = db.query(Azienda).first()
    if not a:
        return "", None
    return a.ragione_sociale or "", a.logo_path

def genera_codice_verifica() -> str:
    return secrets.token_hex(8).upper()

def genera_pdf(path: str, *, nome_discente: str, titolo_corso: str,
               data_evento: str, codice_verifica: str, azienda: str = "", logo_path: str = None):
    """Layout fisso di riserva, usato quando il corso non ha un template
    grafico assegnato (né esiste un template aziendale di default)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, width / 2 - 60, height - 90, width=120, height=50,
                         preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            pass
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

def genera_pdf_da_template(path: str, *, template, valori: dict):
    """Sfondo grafico del template (immagine) + campi posizionati dall'editor
    drag-and-drop (api/certificato_templates.py), con le coordinate convertite
    dai pixel del canvas dell'editor ai punti PDF in base alla dimensione
    reale dell'immagine caricata."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img_w_px = template.larghezza_px or 1000
    img_h_px = template.altezza_px or 700
    pdf_w = A4[0]
    pdf_h = pdf_w * img_h_px / img_w_px
    scala = pdf_w / img_w_px

    c = canvas.Canvas(path, pagesize=(pdf_w, pdf_h))
    if template.immagine_path and os.path.exists(template.immagine_path):
        try:
            c.drawImage(template.immagine_path, 0, 0, width=pdf_w, height=pdf_h)
        except Exception:
            pass

    for campo in (template.campi or []):
        testo = valori.get(campo.get("chiave"), "")
        if not testo:
            continue
        x = (campo.get("x") or 0) * scala
        y = pdf_h - (campo.get("y") or 0) * scala  # editor: y dall'alto; PDF: y dal basso
        font_size = campo.get("font_size") or 14
        grassetto = bool(campo.get("bold"))
        allineamento = campo.get("align") or "left"
        colore = campo.get("colore") or "#000000"
        c.setFont("Helvetica-Bold" if grassetto else "Helvetica", font_size)
        try:
            c.setFillColor(HexColor(colore))
        except Exception:
            c.setFillColor(HexColor("#000000"))
        if allineamento == "center":
            c.drawCentredString(x, y, str(testo))
        elif allineamento == "right":
            c.drawRightString(x, y, str(testo))
        else:
            c.drawString(x, y, str(testo))
    c.showPage()
    c.save()

def _docenti_nomi(db, edizione) -> str:
    if not edizione:
        return ""
    righe = (
        db.query(User.full_name)
        .join(EdizioneDocente, EdizioneDocente.user_id == User.id)
        .filter(EdizioneDocente.edizione_id == edizione.id)
        .order_by(EdizioneDocente.ruolo)  # titolare prima di co_docente (ordine alfabetico dei value)
        .all()
    )
    return ", ".join(r[0] for r in righe)

def _template_per_corso(db, corso):
    from ..models.certificato_template import CertificatoTemplate
    if corso and corso.certificato_template_id:
        t = db.query(CertificatoTemplate).filter(CertificatoTemplate.id == corso.certificato_template_id).first()
        if t and t.immagine_path:
            return t
    return db.query(CertificatoTemplate).filter(
        CertificatoTemplate.is_default == True, CertificatoTemplate.immagine_path.isnot(None)
    ).first()

def crea_certificato(db, iscrizione, corso, nome_discente: str, azienda: str = "",
                      logo_path: str = None, edizione=None) -> Certificato:
    codice = genera_codice_verifica()
    filename = f"{iscrizione.id}_{codice}.pdf"
    path = os.path.join(CERT_DIR, filename)
    template = _template_per_corso(db, corso)
    if template:
        valori = {
            "nome_discente": nome_discente,
            "titolo_corso": corso.titolo if corso else "",
            "data_evento": datetime.utcnow().strftime("%d/%m/%Y"),
            "ore_corso": str(edizione.ore_dichiarate) if edizione and edizione.ore_dichiarate else "",
            "azienda_nome": azienda,
            "ente_erogatore": (edizione.ente_erogatore if edizione else "") or "",
            "docente_nome": _docenti_nomi(db, edizione),
            "codice_verifica": codice,
        }
        genera_pdf_da_template(path, template=template, valori=valori)
    else:
        genera_pdf(path, nome_discente=nome_discente, titolo_corso=corso.titolo if corso else "",
                   data_evento=datetime.utcnow().strftime("%d/%m/%Y"),
                   codice_verifica=codice, azienda=azienda, logo_path=logo_path)
    cert = Certificato(
        iscrizione_id=iscrizione.id,
        tipo=TipoCertificato.base,
        codice_verifica=codice,
        pdf_path=path,
    )
    db.add(cert)
    db.flush()
    return cert
