# Piattaforma E-Learning aziendale

Piattaforma per gestire e **rendicontare** la formazione interna: corsi, sessioni (in presenza, remote, miste, video, esterne), percorsi, scadenze e rinnovi, attestati verificabili, registro per audit e ispezioni. Non eroga la formazione svolta da enti accreditati: la rendiconta (attestati esterni, registro, matrice formativa).

Versione corrente: vedi `backend/app/version.py` e la pagina *Informazioni* dell'app. Storia delle versioni: `backend/app/api/about.py` (changelog) e `ROADMAP.md`.

## Cosa serve
- Un server con **Docker** e **Docker Compose**.
- Un dominio o un indirizzo interno, e un **proxy HTTPS** davanti alla piattaforma (non incluso: lo gestisce l'infrastruttura).
- Facoltativi: un server **SMTP** (email di notifica, inviti, reset password), un tenant **Microsoft Entra ID** (accesso aziendale, sincronizzazione utenti, presenze Teams).

## Installazione
```bash
cp .env.example .env
# modifica .env: almeno POSTGRES_PASSWORD e SECRET_KEY (un valore lungo e casuale:
#   python3 -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up -d --build
```
La piattaforma risponde sulla porta **2018** del server (`http://<server>:2018`). Gli utenti devono raggiungerla dall'indirizzo **HTTPS pubblico** messo dal proxy (per esempio `https://formazione.tuaazienda.it`), che è anche l'indirizzo da indicare in *Impostazioni → Piattaforma* (serve ai link nelle email e all'accesso aziendale). La porta 2018 non va esposta direttamente: tienila raggiungibile solo dal proxy o dalla rete interna (configurazione di rete e firewall, non della piattaforma). Al primo accesso compare la pagina *Primo avvio*: crea l'utente **Admin tecnico**. La password deve avere almeno 14 caratteri, con una maiuscola, un numero e un carattere speciale.

Poi segui la [guida dell'amministratore](docs/guida-amministratore.md) per la configurazione iniziale.

### Cosa parte
| Servizio | Ruolo |
|---|---|
| `db` | PostgreSQL 16 |
| `backend` | API (FastAPI) e job notturni; applica da solo le migrazioni all'avvio |
| `frontend` | interfaccia React |
| `nginx` | unisce sito e API; è l'unico servizio esposto (porta 2018) |

I dati stanno in tre **volumi Docker con nome**: `postgres_data` (database), `uploads` (attestati, loghi, allegati), `videos` (video). Il backup deve includerli (vedi sotto).

## Configurazione (`.env`)
Tutto ciò che riguarda l'infrastruttura si imposta **solo qui**, mai dall'interfaccia: la piattaforma mostra lo stato (configurato o no) ma non le credenziali.

| Variabile | A cosa serve |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | database |
| `SECRET_KEY` | firma delle sessioni: lungo, casuale, segreto. Cambiarlo chiude tutte le sessioni |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_MITTENTE`, `SMTP_TLS` | invio email (notifiche, inviti, reset password). Vuoto = nessuna email |
| `SSO_ISSUER`, `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`, `SSO_PUBLIC_URL`, `SSO_LABEL`, `SSO_PROVISIONA_UTENTI` | accesso aziendale (OpenID Connect). Redirect da registrare nell'IdP: `<SSO_PUBLIC_URL>/api/auth/sso/callback` |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` | Microsoft Graph (riunioni Teams, presenze) |
| `ENTRA_SYNC_GRUPPO_ID`, `ENTRA_SYNC_AUTO` | sincronizzazione utenti da Entra ID (permessi `User.Read.All`, `GroupMember.Read.All`) |
| `PROXY_FIDUCIARI` | reti/indirizzi dei proxy davanti alla piattaforma, separati da virgola |
| `PROXY_CLOUDFLARE` | `true` solo se davanti c'è Cloudflare |

### Proxy e indirizzo IP del client
L'IP del client serve all'audit e ai limiti di tentativi. La piattaforma **non crede agli header** che lo dichiarano, a meno che la connessione arrivi da un indirizzo elencato in `PROXY_FIDUCIARI`. Dietro un proxy aziendale indica qui l'indirizzo con cui il proxy raggiunge la piattaforma (e il proxy deve valorizzare `X-Forwarded-For`). Se non lo fai, tutto funziona ma l'audit mostra l'IP del proxy.

### URL pubblico
Impostalo nella pagina *Piattaforma* dell'app: serve per i link nelle email (inviti, reset password, notifiche).

## Aggiornamento
```bash
# 1. copia di sicurezza del database (vedi sotto)
git pull
docker compose up -d --build
```
Le **migrazioni dello schema** partono da sole all'avvio, una volta sola anche con più processi. Un database nato prima dell'introduzione delle migrazioni viene riconosciuto e portato avanti senza perdere dati.

## Backup
Il backup è compito dell'infrastruttura, non della piattaforma. Servono:
- il **database**: `docker exec elearning-db pg_dump -U <utente> <database> > backup.sql`;
- i volumi **`uploads`** e **`videos`**;
- il file **`.env`** (contiene i segreti: conservalo a parte).

La pagina *Impostazioni → Configurazione* esporta e reimporta solo le **impostazioni** (gruppi, corsi, percorsi, etichette, dati aziendali): serve a ricostruire una configurazione o a spostarla da un ambiente all'altro, non sostituisce il backup.

## Sviluppo e test
```bash
docker compose --profile test run --rm tests          # tutti i test (circa 4 minuti)
docker compose --profile test run --rm tests pytest tests/test_accessi.py   # un file
```
I test usano un database separato (`<nome>_test`, creato al volo) e non toccano mai i dati veri.

**Modificare i modelli del database** richiede una migrazione: dal container del backend, `alembic revision --autogenerate -m "cosa cambia"`, poi rivedere il file in `backend/migrations/versions`. Un test fallisce se una migrazione manca.

### Struttura
```
backend/app/api/         endpoint (uno per area)
backend/app/models/      tabelle
backend/app/services/    logica condivisa (audit, notifiche, rinnovi, sincronizzazione...)
backend/migrations/      migrazioni dello schema (Alembic)
backend/tests/           test automatici
frontend/src/pages/      pagine; components/ elementi riusati
nginx/nginx.conf         proxy interno
docs/                    guide
ROADMAP.md               storia e prossimi passi
```

### Job pianificati
Ogni notte: notifiche di scadenza e promemoria (all'avvio e ogni 24 ore), rinnovi automatici dei corsi (02:00), sincronizzazione Entra se attiva (02:30). Esiti e storico: pagina *Stato piattaforma*.

## Storia del progetto
La cronologia dei commit fino alla 1.8.2 è una ricostruzione per fasi, non una registrazione fedele: leggi [`docs/storico.md`](docs/storico.md) prima di usarla come riferimento.

## Ruoli
Tre ruoli fissi: **Admin tecnico** (configura e amministra), **Ufficio Formazione** (gestisce corsi, sessioni, percorsi, registro) e **utente**. *Responsabile* (chi guida un ufficio) e *docente* (chi tiene una sessione) non sono ruoli: derivano dalla struttura degli uffici e dalle sessioni.
