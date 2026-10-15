from datetime import datetime, timedelta, timezone

def _fmt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _escape(testo: str) -> str:
    return (testo or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")

def evento_edizione(edizione, corso_titolo: str):
    """Un VEVENT per una sessione con data fissata, o None se non ancora
    pianificata. UID stabile sull'id dell'edizione: ogni volta che la si
    ri-genera (data cambiata, nuovo invio) resta lo stesso evento agli occhi
    del client calendario invece di diventarne uno duplicato."""
    if not edizione.data_inizio:
        return None
    inizio = edizione.data_inizio
    fine = edizione.data_fine or (inizio + timedelta(hours=1))
    luogo = edizione.luogo or edizione.teams_join_url or ""
    righe = [
        "BEGIN:VEVENT",
        f"UID:edizione-{edizione.id}@piattaforma-formazione",
        f"DTSTAMP:{_fmt(datetime.now(timezone.utc))}",
        f"DTSTART:{_fmt(inizio)}",
        f"DTEND:{_fmt(fine)}",
        f"SUMMARY:{_escape(corso_titolo)}",
    ]
    if luogo:
        righe.append(f"LOCATION:{_escape(luogo)}")
    if edizione.note:
        righe.append(f"DESCRIPTION:{_escape(edizione.note)}")
    righe.append("END:VEVENT")
    return "\r\n".join(righe)

def costruisci_ics(eventi) -> bytes:
    corpo = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Piattaforma Formazione//IT",
        "CALSCALE:GREGORIAN",
        *eventi,
        "END:VCALENDAR",
    ])
    return corpo.encode("utf-8")
