"""Integrazione Microsoft Graph per le presenze Teams.

Se le credenziali app (GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET) non sono
configurate, tutte le funzioni sono no-op e il chiamante deve ricadere sul
flusso manuale (incolla link riunione / carica report) - vedi ModalitaTeams
in models/edizione.py. Nessuna feature è bloccata dall'assenza del consenso
admin M365, è solo meno automatica.
"""
import httpx
from ..config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

async def _get_token() -> str | None:
    if not settings.graph_enabled:
        return None
    url = f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": settings.GRAPH_CLIENT_ID,
        "client_secret": settings.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=data, timeout=15)
        if resp.status_code != 200:
            return None
        return resp.json().get("access_token")

async def crea_riunione(organizer_upn: str, subject: str, start_iso: str, end_iso: str) -> dict | None:
    """Modalità 'auto': la piattaforma crea la riunione per conto del docente.
    Richiede permesso OnlineMeetings.ReadWrite.All con consenso admin."""
    token = await _get_token()
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/users/{organizer_upn}/onlineMeetings",
            json={"subject": subject, "startDateTime": start_iso, "endDateTime": end_iso},
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        if resp.status_code not in (200, 201):
            return None
        data = resp.json()
        return {"id": data["id"], "joinUrl": data.get("joinWebUrl")}

async def scarica_report_presenze(organizer_upn: str, meeting_id: str) -> list[dict] | None:
    """Ritorna la lista attendanceRecords dell'ultimo report disponibile, o None
    se Graph non è configurato/raggiungibile - il chiamante deve allora proporre
    il fallback manuale."""
    token = await _get_token()
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        reports = await client.get(
            f"{GRAPH_BASE}/users/{organizer_upn}/onlineMeetings/{meeting_id}/attendanceReports",
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        if reports.status_code != 200:
            return None
        values = reports.json().get("value", [])
        if not values:
            return None
        report_id = values[-1]["id"]
        records = await client.get(
            f"{GRAPH_BASE}/users/{organizer_upn}/onlineMeetings/{meeting_id}/attendanceReports/{report_id}/attendanceRecords",
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        if records.status_code != 200:
            return None
        return records.json().get("value", [])
