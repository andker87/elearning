"""Importazione massiva di utenti da CSV o da Excel (.xlsx), con anteprima.

Regole:
- una riga e' scartata (errore) solo se non si puo' usare: email, nome o cognome mancanti, email gia' presente,
  organizzazione o password o data non valide, contraddizioni (un esterno con ufficio o con permessi);
- un ufficio o una mansione che non esistono NON scartano la riga: la persona si crea senza e la riga porta un avviso;
  lo stesso per l'ufficio lasciato vuoto. Uffici e mansioni non si creano mai da soli (un errore di battitura
  creerebbe voci inutili);
- con `anteprima` si fa tutto davvero dentro la transazione e poi si annulla: il riepilogo non puo' discostarsi dal risultato,
  e non parte nessuna email.
"""
import csv
import io
import zipfile
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import audit as audit_svc
from .auth import hash_password
from .configurazione import _percorso_gruppo
from .email import dopo_il_commit
from .impronte import impronta
from .inviti import crea_link_invito, invia_invito
from .offboarding import disattiva_utente, invita_promossi
from .password_policy import REQUISITI_PASSWORD, genera_password_temporanea, password_valida
from .percorsi_sync import sincronizza_assegnazioni
from ..models.group import Group
from ..models.mansione import Mansione
from ..models.organizzazione import Organizzazione
from ..models.user import User

LIMITE_BYTE = 5 * 1024 * 1024
LIMITE_ESPANSO = 50 * 1024 * 1024      # un .xlsx e' uno zip: si guarda quanto diventa, prima di aprirlo
LIMITE_RIGHE = 20000
COLONNE_NUOVI = ["email", "nome", "cognome", "ufficio", "mansioni", "admin", "formazione", "formatore",
                 "is_external", "organizzazione", "data_ingresso", "password"]
_VERO = ("true", "si", "sì", "1", "yes", "x", "s")


def si(valore) -> bool:
    return (valore or "").strip().lower() in _VERO


# --- lettura del file -------------------------------------------------------------------------------

def _cella(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _leggi_csv(contenuto: bytes) -> list:
    try:
        testo = contenuto.decode("utf-8-sig")
    except UnicodeDecodeError:
        testo = contenuto.decode("cp1252", errors="replace")   # «CSV» di Excel in italiano: codifica di Windows
    righe = testo.splitlines()
    if not righe:
        raise HTTPException(400, "File vuoto")
    delimitatore = ";" if righe[0].count(";") > righe[0].count(",") else ","
    lettore = csv.reader(io.StringIO(testo), delimiter=delimitatore)
    return [(n, [c for c in riga]) for n, riga in enumerate(lettore, start=1)]


def _leggi_xlsx(contenuto: bytes) -> list:
    try:
        with zipfile.ZipFile(io.BytesIO(contenuto)) as z:
            if sum(i.file_size for i in z.infolist()) > LIMITE_ESPANSO:
                raise HTTPException(400, "Il file Excel è troppo grande")
    except zipfile.BadZipFile:
        raise HTTPException(400, "Il file non è un Excel (.xlsx) valido")
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(contenuto), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "Il file Excel non si riesce a leggere: salvalo di nuovo come .xlsx o come CSV")
    try:
        foglio = wb["Utenti"] if "Utenti" in wb.sheetnames else wb.worksheets[0]
        return [(n, list(riga)) for n, riga in enumerate(foglio.iter_rows(values_only=True), start=1)]
    finally:
        wb.close()


def leggi_tabella(nome_file: str, contenuto: bytes) -> tuple:
    """(intestazioni in minuscolo, [(numero di riga, {intestazione: testo})]) da un CSV o da un .xlsx.
    Il tipo si riconosce dal contenuto, non dal nome: un Excel salvato con estensione .csv funziona lo stesso."""
    if len(contenuto) > LIMITE_BYTE:
        raise HTTPException(400, "Il file è troppo grande (massimo 5 MB)")
    nome = (nome_file or "").lower()
    if contenuto[:4] == b"PK\x03\x04":
        grezze = _leggi_xlsx(contenuto)
    elif nome.endswith(".xls") or contenuto[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise HTTPException(400, "Il formato Excel vecchio (.xls) non è supportato: aprilo in Excel e salvalo come «Cartella di lavoro di Excel (.xlsx)» oppure come CSV")
    else:
        grezze = _leggi_csv(contenuto)
    grezze = [(n, r) for n, r in grezze if any(_cella(c) for c in r)]          # righe vuote saltate, la numerazione resta quella del file
    if not grezze:
        raise HTTPException(400, "File vuoto")
    if len(grezze) > LIMITE_RIGHE:
        raise HTTPException(400, f"Troppe righe: massimo {LIMITE_RIGHE} per file")
    intestazioni = [_cella(c).lower() for c in grezze[0][1]]
    righe = []
    for n, r in grezze[1:]:
        righe.append((n, {intestazioni[i]: _cella(c) for i, c in enumerate(r) if i < len(intestazioni) and intestazioni[i]}))
    return [i for i in intestazioni if i], righe


# --- nuovi utenti -----------------------------------------------------------------------------------

def _riga(n, email, esito, messaggio, avvisi=None, **extra):
    return {"riga": n, "email": email, "esito": esito, "messaggio": messaggio, "avvisi": avvisi or [], **extra}


def elabora_nuovi(db: Session, request, admin, intestazioni: list, righe: list, anteprima: bool) -> dict:
    if "full_name" in intestazioni and "cognome" not in intestazioni:
        raise HTTPException(400, "La colonna «full_name» non esiste più: usa due colonne, «nome» e «cognome»")
    if not {"email", "nome", "cognome"} <= set(intestazioni):
        raise HTTPException(400, "Intestazioni richieste: email, nome, cognome")
    if "role" in intestazioni or "gruppi" in intestazioni:
        raise HTTPException(400, "Le colonne «role» e «gruppi» non esistono più: usa «admin», «formazione», «formatore» (sì/no), «ufficio» e «mansioni»")

    uffici = db.query(Group).all()
    per_id = {g.id: g for g in uffici}
    uffici_per_percorso = {_percorso_gruppo(g, per_id).lower(): g for g in uffici}
    uffici_per_nome = {}
    for g in uffici:
        uffici_per_nome.setdefault(g.name.lower(), []).append(g)
    mansioni_tutte = {m.name.lower(): m for m in db.query(Mansione).all()}
    org_tutte = {o.ragione_sociale.lower(): o for o in db.query(Organizzazione).all()}
    visti = set()          # la stessa email due volte nello stesso file

    from ..api.auth import _assegna_mansioni, _assegna_ufficio   # le stesse regole della scheda utente
    out, creati = [], 0
    for n, row in righe:
        email, nome, cognome = row.get("email", ""), row.get("nome", ""), row.get("cognome", "")
        if not email or not nome or not cognome:
            out.append(_riga(n, email, "errore", "email, nome o cognome mancante"))
            continue
        if db.query(User).filter(User.email_idx == impronta(email)).first() or impronta(email) in visti:
            out.append(_riga(n, email, "errore", "email già esistente"))
            continue
        is_external = si(row.get("is_external"))
        org = None
        if row.get("organizzazione"):
            org = org_tutte.get(row["organizzazione"].lower())
            if not org:
                out.append(_riga(n, email, "errore", f"organizzazione \"{row['organizzazione']}\" non trovata"))
                continue
        if is_external and not org:
            out.append(_riga(n, email, "errore", "utente esterno senza organizzazione"))
            continue
        is_admin, is_formazione, is_formatore = (si(row.get(c)) for c in ("admin", "formazione", "formatore"))
        if is_external and (is_admin or is_formazione):
            out.append(_riga(n, email, "errore", "un utente esterno non può essere Admin o Formazione"))
            continue
        if row.get("ufficio") and is_external:
            out.append(_riga(n, email, "errore", "un utente esterno non ha ufficio"))
            continue
        data_ingresso = None
        if row.get("data_ingresso"):
            try:
                data_ingresso = datetime.strptime(row["data_ingresso"], "%Y-%m-%d")
            except ValueError:
                out.append(_riga(n, email, "errore", "data_ingresso non valida (formato YYYY-MM-DD)"))
                continue
        password = row.get("password") or genera_password_temporanea()
        if not password_valida(password):
            out.append(_riga(n, email, "errore", f"password non valida: richiesti {REQUISITI_PASSWORD}"))
            continue

        avvisi, ufficio = [], None
        nome_ufficio = row.get("ufficio", "")
        if nome_ufficio:
            ufficio = uffici_per_percorso.get(nome_ufficio.lower())
            if not ufficio:
                candidati = uffici_per_nome.get(nome_ufficio.lower(), [])
                if len(candidati) > 1:
                    avvisi.append(f"ufficio «{nome_ufficio}» ambiguo (esiste in più rami): scrivi il percorso intero, per esempio Produzione / Linea 2. Creato senza ufficio")
                elif candidati:
                    ufficio = candidati[0]
                else:
                    avvisi.append(f"ufficio «{nome_ufficio}» non presente. Creato senza ufficio")
        elif not is_external and not is_admin:
            avvisi.append("ufficio non indicato. Creato senza ufficio")

        u = User(
            email=email, nome=nome, cognome=cognome,
            # nell'anteprima si annulla tutto: niente costo di bcrypt per ogni riga
            hashed_password="anteprima" if anteprima else hash_password(password),
            is_admin=is_admin, is_formazione=is_formazione, is_formatore=is_formatore, is_external=is_external,
            organizzazione_id=org.id if org else None,
            data_ingresso=data_ingresso,
            origine_credenziali="locale",
            password_da_cambiare=True,
        )
        try:
            with db.begin_nested():
                db.add(u)
                db.flush()
        except IntegrityError:
            if not db.query(User).filter(User.email_idx == impronta(email)).first():
                raise
            out.append(_riga(n, email, "errore", "email già esistente"))
            continue
        visti.add(impronta(email))

        _assegna_ufficio(u.id, ufficio.id if ufficio else None, db)
        if row.get("mansioni") and not is_external:
            mansione_ids = []
            for nome_mansione in row["mansioni"].replace("|", ";").split(";"):
                nome_mansione = nome_mansione.strip()
                if not nome_mansione:
                    continue
                m = mansioni_tutte.get(nome_mansione.lower())
                if m:
                    mansione_ids.append(str(m.id))
                else:
                    avvisi.append(f"mansione «{nome_mansione}» non presente. Creato senza quella mansione")
            _assegna_mansioni(u.id, mansione_ids, db)

        inviata = False
        if not anteprima:
            link = crea_link_invito(db, u)
            db.flush()
            inviata = bool(link)
            if link:
                dopo_il_commit(db, invia_invito, email, u.full_name, link)   # il link, mai la password; parte solo a commit riuscito
        creati += 1
        out.append(_riga(n, email, "creato", "creato" if not avvisi else "creato, con avvisi: " + "; ".join(avvisi), avvisi,
                         nome=f"{nome} {cognome}", email_inviata=inviata,
                         password=None if (anteprima or inviata) else password))

    if anteprima:
        db.rollback()
    else:
        if request is not None:
            audit_svc.log_from_request(db, request, admin, "CREATE", entity_type="user", entity_name=f"import: {creati} utenti creati")
        sincronizza_assegnazioni(db)
        db.commit()
    return {"anteprima": anteprima, "totale": len(out), "creati": creati,
            "con_avvisi": sum(1 for r in out if r["esito"] == "creato" and r["avvisi"]),
            "errori": sum(1 for r in out if r["esito"] == "errore"), "righe": out}


# --- cessati ----------------------------------------------------------------------------------------

def elabora_cessati(db: Session, request, admin, intestazioni: list, righe: list, anteprima: bool) -> dict:
    if "email" not in intestazioni:
        raise HTTPException(400, "Intestazione richiesta: email")
    out, disattivati, promossi_tutti = [], 0, []
    for n, row in righe:
        email = row.get("email", "")
        if not email:
            out.append(_riga(n, email, "errore", "email mancante"))
            continue
        u = db.query(User).filter(User.email_idx == impronta(email)).first()
        if not u:
            out.append(_riga(n, email, "ignorato", "email non trovata"))
            continue
        if not u.is_active:
            out.append(_riga(n, email, "ignorato", "già disattivato"))
            continue
        if u.is_admin:
            out.append(_riga(n, email, "errore", "Admin: non si disattiva da un elenco"))
            continue
        r = disattiva_utente(db, u)
        promossi_tutti.extend(r["promossi"])
        disattivati += 1
        messaggio = "disattivato"
        if r["posti_liberati"]:
            messaggio += f" ({r['posti_liberati']} iscrizioni aperte annullate)"
        avvisi = list(r["avvisi"])
        if avvisi:
            messaggio += " - attenzione: " + "; ".join(avvisi)
        out.append(_riga(n, email, "disattivato", messaggio, avvisi, nome=u.full_name))
    if anteprima:
        db.rollback()
    else:
        if request is not None:
            audit_svc.log_from_request(db, request, admin, "UPDATE", entity_type="user", entity_name=f"import cessati: {disattivati} utenti disattivati")
        db.commit()
        invita_promossi(db, promossi_tutti)
    return {"anteprima": anteprima, "totale": len(out), "creati": 0, "disattivati": disattivati,
            "con_avvisi": sum(1 for r in out if r["esito"] == "disattivato" and r["avvisi"]),
            "errori": sum(1 for r in out if r["esito"] == "errore"), "righe": out}


# --- modelli da scaricare ---------------------------------------------------------------------------

def _percorsi_uffici(db: Session) -> list:
    uffici = db.query(Group).all()
    per_id = {g.id: g for g in uffici}
    return sorted((_percorso_gruppo(g, per_id) for g in uffici), key=str.casefold)


def modello(db: Session, formato: str, modo: str) -> tuple:
    """(contenuto, nome del file, tipo) del modello da scaricare, con i nomi veri di uffici e mansioni del sistema."""
    percorsi = _percorsi_uffici(db)
    mansioni = sorted((m.name for m in db.query(Mansione).filter(Mansione.is_active == True).all()), key=str.casefold)  # noqa: E712
    if modo == "cessati":
        intestazione, esempio, base = ["email"], ["mario.rossi@azienda.it"], "modello-cessati"
    else:
        intestazione = COLONNE_NUOVI
        esempio = ["mario.rossi@azienda.it", "Mario", "Rossi", percorsi[0] if percorsi else "Nome dell'ufficio", mansioni[0] if mansioni else "",
                   "no", "no", "no", "no", "", "2026-01-15", ""]
        base = "modello-nuovi-utenti"
    if formato == "csv":
        testo = "﻿" + "\r\n".join(";".join(r) for r in (intestazione, esempio)) + "\r\n"     # «;»: Excel in italiano lo apre in colonne
        return testo.encode("utf-8"), base + ".csv", "text/csv; charset=utf-8"

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Utenti"
    ws.append(intestazione)
    ws.append(esempio)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", start_color="DDEBF7")
    for c in ws[2]:
        c.font = Font(italic=True, color="808080")
    for i, nome in enumerate(intestazione, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, len(nome) + 4)
    ws.freeze_panes = "A2"
    for riga in ws.iter_rows():
        for c in riga:
            if isinstance(c.value, str):
                c.data_type = "s"            # mai una formula, nemmeno se un nome comincia con «=»
    istruzioni = wb.create_sheet("Istruzioni")
    testi = ([
        "Elenco delle persone da disattivare: una per riga, nella colonna «email» del foglio «Utenti».",
        "Cancella la riga di esempio e compila le tue righe. Non modificare l'intestazione.",
        "Gli Admin non si disattivano da qui.",
    ] if modo == "cessati" else [
        "Compila il foglio «Utenti», una persona per riga. Cancella la riga di esempio. Non modificare l'intestazione.",
        "Obbligatori: email, nome, cognome. L'ufficio è obbligatorio per gli utenti interni che non sono Admin.",
        "Ufficio: scrivilo come nel foglio «Uffici» (la colonna ha un menu a tendina). Se un nome si ripete in più rami usa il percorso intero.",
        "Mansioni: nomi presenti nel foglio «Mansioni», separati da «;» (per esempio Preposto;Antincendio).",
        "admin, formazione, formatore, is_external: scrivi sì o no (vuoto = no).",
        "Gli esterni (is_external = sì) sono docenti di una società terza: servono l'organizzazione (ragione sociale esatta) e non hanno ufficio né mansioni.",
        "data_ingresso: AAAA-MM-GG (per esempio 2026-01-15), facoltativa. password: facoltativa (se manca la persona sceglie la sua con un link).",
        "Uffici e mansioni non vengono mai creati dal file: se un nome non esiste la persona viene creata senza, e te lo diciamo nel riepilogo prima di confermare.",
    ])
    for t in testi:
        istruzioni.append([t])
    istruzioni.column_dimensions["A"].width = 120
    if modo != "cessati":
        fu = wb.create_sheet("Uffici")
        fu.append(["Ufficio (percorso)"])
        for p in percorsi:
            fu.append([p])
        fu["A1"].font = Font(bold=True)
        fu.column_dimensions["A"].width = 60
        fm = wb.create_sheet("Mansioni")
        fm.append(["Mansione"])
        for m in mansioni:
            fm.append([m])
        fm["A1"].font = Font(bold=True)
        fm.column_dimensions["A"].width = 40
        for foglio in (fu, fm):
            for riga in foglio.iter_rows(min_row=2):
                for c in riga:
                    c.data_type = "s"
        if percorsi:
            dv = DataValidation(type="list", formula1=f"=Uffici!$A$2:$A${len(percorsi) + 1}", allow_blank=True, showErrorMessage=False)
            ws.add_data_validation(dv)
            dv.add("D2:D2000")
        sino = DataValidation(type="list", formula1='"sì,no"', allow_blank=True, showErrorMessage=False)
        ws.add_data_validation(sino)
        for col in ("F", "G", "H", "I"):
            sino.add(f"{col}2:{col}2000")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), base + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
