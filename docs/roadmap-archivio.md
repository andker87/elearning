# Archivio della roadmap

Sezioni della [roadmap](../ROADMAP.md) già spedite o chiuse, spostate qui senza modifiche. Contenuto:

- Stato attuale (cosa esiste già)
- H. Integrazione calendario — SPEDITO
- M. Comunicazioni/annunci su una sessione — SPEDITO
- N. Lista d'attesa — SPEDITO
- O. Duplica sessione — SPEDITO
- P. Auto-iscrizione dal catalogo — SPEDITO
- Q. Sondaggio di fabbisogno formativo (periodico) — SPEDITO
- R. Autenticazione aziendale (SSO) — SPEDITO
- S. Audit delle azioni dei discenti — SPEDITO
- T. Uniformità con altre piattaforme interne — SPEDITO
- U. Sicurezza degli accessi — SPEDITO (13/10/2026, v1.3.0)
- V. Matrice formativa e pacchetto per l'ispezione — SPEDITO (13/10/2026, v1.3.0)
- Z. Revisione del codice (14/10/2026, v1.7.2)
- Z2. Seconda revisione del codice (14/10/2026, v1.8.1)
- Z3. Terza revisione del codice (14/10/2026, v1.8.2)
- Z4. Quarta revisione del codice (14/10/2026, v1.8.3)
- Z5. Rilievi di CodeRabbit sulla cronologia pubblica (v1.8.4 e seguenti)
- Y. Etichette dei corsi — SPEDITO (14/10/2026, v1.7.0)
- X. Configurazione esportabile/importabile — SPEDITO (14/10/2026, v1.6.0)

## Stato attuale (cosa esiste già)

- **Identità**: Utenti (interni/esterni + organizzazione), Ruoli di sistema (Admin,
  Ufficio Formazione, Utenti — ruoli fissi; responsabile e docente derivano dall'incarico), Gruppi
  liberi con sottogruppi (per rolling massivo), Azienda, Impostazioni utente
  (profilo + cambio password, pronta per futura integrazione SSO/dominio).
- **Catalogo**: Corsi (con validità/rinnovo, policy test non superato opzionale),
  Percorsi formativi (step con propedeuticità, motivo dell'obbligo, trigger
  automatico su gruppo/ingresso in azienda, editabili), Società di formazione
  esterne.
- **Erogazione**: Sessioni nelle 5 modalità (presenza/ibrida/remoto/video/esterna),
  check-in discente+validazione o registro docente, integrazione Teams
  (auto/manuale, con fallback), player video con transcodifica ffmpeg, capitoli,
  sottotitoli, anti-skip lato server.
- **Verifica**: Motore test/quiz personalizzabile, gradimento post-corso,
  certificati con codice di verifica pubblico, report CSV per sessione.
- **Operatività**: Notifiche in-app (scadenze, promemoria, sessioni imminenti) con
  deduplica, scheduler giornaliero (esiti tracciati in `job_runs`), email SMTP
  (solo da ambiente), notifiche push, comunicazioni agli iscritti di una
  sessione, lista d'attesa, auto-iscrizione dal catalogo (con approvazione del
  responsabile), duplica sessione, sondaggio di fabbisogno formativo.
- **Calendario**: download .ics per sessione, feed iCal personale abbonabile
  (Outlook/Google), invito email con .ics all'iscrizione confermata (solo se
  SMTP configurato).
- **PWA**: installabile con banner proattivi compatti (installazione e
  permesso notifiche), sidebar collassabile e ridimensionabile.
- **Compliance/reportistica**: registro formazione, versionamento corsi,
  template attestati drag-and-drop, Dashboard Ufficio Formazione, Dashboard KPI,
  export CSV/Excel/PDF, gerarchia uffici/responsabili.
- **Dashboard per persona**: Utente (i miei corsi / storico), Docente (le mie
  sessioni), Responsabile (risorse, richieste corso, fabbisogno), Ufficio Training
  (dashboard, sessioni/corsi/video/percorsi/registro/template), Amministrazione
  (utenti/ruoli/gruppi/società esterne/azienda/stato piattaforma/audit log).
- **Audit**: registro eventi con filtri ed export CSV, copertura estesa alle
  azioni amministrative e di gestione sessioni, IP reale dietro tunnel.
- **Hardening**: container non-root (backend `app`, frontend `node`), permessi
  volumi corretti.
- **Fix**: i download CSV/PDF (report iscrizioni/gradimenti, report test,
  attestati, registro formazione) usavano `<a href>` puro verso `/api/...`,
  che non porta l'header Authorization — risultato: 401 per chiunque provasse
  a scaricarli dal browser. Ora passano tutti da `downloadFile()` in
  `frontend/src/api.js` (fetch autenticato + blob), stesso punto per ogni
  nuovo export futuro.

### H. Integrazione calendario — SPEDITO
- [x] Scelto con il committente l'approccio a basso sforzo (iCal, no OAuth/credenziali
  da richiedere): niente libreria esterna, `services/calendario.py` costruisce
  a mano i VEVENT (UID stabile `edizione-{id}@piattaforma-formazione` — una
  data che cambia aggiorna lo stesso evento nel calendario invece di
  duplicarlo).
  **Tre punti d'accesso**: (1) `GET /api/edizioni/{id}/calendario.ics`,
  bottone "📅 Aggiungi al calendario" in `EdizioneDetail.js` per il singolo
  evento; (2) feed personale abbonabile `GET /api/calendario/feed.ics?token=`
  — aggrega tutte le sessioni con data in cui l'utente è iscritto o docente,
  si aggiorna da solo in Outlook/Google Calendar senza bisogno di OAuth
  perché il token sta nell'URL stesso (endpoint pubblico, niente Bearer: è il
  client calendario a interrogarlo periodicamente, non una persona davanti a
  un browser) — `User.calendar_token`, generato al primo `GET
  /api/calendario/url`, rigenerabile da Impostazioni utente ("Il mio
  calendario", con copia-link); (3) invito via email con `.ics` in allegato,
  **agganciato alla configurazione SMTP come chiesto dal committente**:
  `services/notifiche.py` (`invia_invito_calendario`) controlla
  `settings.smtp_enabled` prima ancora di costruire l'allegato, e
  `invia_email_con_allegato` (nuova funzione in `services/email.py`, stesso
  no-op di `invia_email` se l'SMTP non è configurato) fa lo stesso controllo
  a valle — doppia garanzia, non un singolo punto che se rimosso manda mail a
  vuoto. Agganciato a tutti i punti in cui un'iscrizione diventa confermata:
  iscrizione diretta (`edizioni.py: iscrivi`), auto-iscrizione diretta e su
  approvazione del responsabile (`autoiscrizione.py`), promozione dalla
  lista d'attesa (`iscrizioni.py: promuovi_da_lista_attesa`, ora ritorna
  l'iscrizione promossa al chiamante), e conferma della data per chi era già
  iscritto prima che la sessione fosse pianificata
  (`edizioni.py: pianifica_edizione`). Mai mandato a chi finisce in lista
  d'attesa (non ha ancora un posto/una data da segnare).
  **Verificato**: colonna e indice unico creati (`ix_users_calendar_token`),
  gating SMTP confermato (`invia_invito_calendario` ritorna `False` senza
  eccezioni con SMTP non configurato, com'è in questo ambiente), feed e
  download singolo testati via HTTP reale attraverso nginx (contenuto .ics
  corretto, UID/data/luogo giusti), 404 su token non valido, i quattro punti
  di aggancio (iscrivi, update data su bozza + pianifica, con iscritto
  preesistente) eseguiti via HTTP reale senza errori nei log, build di
  produzione del frontend senza errori, dati di test rimossi senza residui.

### M. Comunicazioni/annunci su una sessione — SPEDITO
- [x] Un avviso (es. "aula cambiata") mandato a tutti gli iscritti di una
  sessione (compresa la lista d'attesa), sui tre canali già pronti:
  notifica in-app, email (sez. D) e push (sez. E). Nuovo modello
  `ComunicazioneEdizione` (storico: oggetto, messaggio, mittente, numero
  destinatari, data) — a differenza delle notifiche automatiche dello
  scheduler, qui niente deduplica: ogni invio è un'azione esplicita di chi
  scrive. `services/notifiche.py` (`invia_comunicazione_edizione`),
  `POST /api/edizioni/{id}/comunicazione` + `GET .../comunicazioni` per lo
  storico. Autorizzati: docente titolare/co-docente della sessione o Ufficio
  Training/Admin tecnico (stesso controllo già usato per le evidenze,
  `_is_docente`). Card "Comunicazioni agli iscritti" in `EdizioneDetail.js`
  (oggetto + messaggio + storico degli invii precedenti).
  **Verificato**: tabella creata da `create_all`, invio reale via HTTP
  attraverso nginx con JWT generato per un Admin tecnico vero (risposta
  `{"inviati": 1}`, notifica in-app creata con il testo corretto, storico
  letto correttamente), permesso negato (403) per un iscritto senza ruolo
  docente/admin sulla sessione, build di produzione del frontend senza
  errori, pulizia dei dati di test confermata.

### N. Lista d'attesa — SPEDITO
- [x] Opzione per edizione (`Edizione.lista_attesa_abilitata`, non globale —
  ogni sessione decide per sé). Capacità centralizzata in
  `services/iscrizioni.py` (`crea_iscrizione_con_capacita`), usata sia
  dall'iscrizione diretta sia dall'auto-iscrizione (sezione P), così il
  comportamento è identico ovunque. Nuovo stato `in_lista_attesa` su
  `Iscrizione`; alla promozione (`promuovi_da_lista_attesa`, FIFO per data)
  serve poter annullare un'iscrizione, che prima non esisteva affatto come
  azione — aggiunto `POST /edizioni/{id}/iscrizioni/{iscrizione_id}/annulla`
  (Ufficio Formazione, l'interessato stesso, o il suo responsabile).

### O. Duplica sessione — SPEDITO
- [x] `POST /edizioni/{id}/duplica`: copia modalità, luogo, posti,
  check-in/Teams mode, video, e i docenti — non le date (da impostare) né
  gli iscritti né il link Teams già creato (specifico alla riunione vecchia).

### P. Auto-iscrizione dal catalogo — SPEDITO
- [x] `Corso.permetti_autoiscrizione` + `Corso.richiedi_approvazione_responsabile`
  (quest'ultima ha senso solo se la prima è attiva, gestito in UI). Se
  l'approvazione è richiesta, nasce una `AutoIscrizioneRichiesta` invece
  della vera `Iscrizione` — tenuta volutamente separata dal motore
  Iscrizione per non aggiungergli un altro stato di limbo; alla conferma del
  responsabile (derivato dalla gerarchia uffici, sezione L) viene creata
  l'iscrizione vera, sempre passando dalla capacità/lista d'attesa
  centralizzata. Se la persona non ha nessun responsabile, l'iscrizione
  viene creata subito (nessuno a cui chiedere approvazione).

### Q. Sondaggio di fabbisogno formativo (periodico) — SPEDITO
- [x] Due flussi, entrambi basati sulla catena di approvazione a cascata
  dell'albero uffici (sezione L), mai fino a un utente finale. Modelli:
  `FabbisognoCampagna`, `FabbisognoCampagnaInvito` (un ufficio è stato
  raggiunto dalla campagna: il suo responsabile deve ancora decidere se
  rispondere o delegare), `FabbisognoRichiesta` (il contenuto, che risale
  l'albero spostando `ufficio_in_revisione_presso_id` al padre ad ogni
  approvazione, finché non diventa `None` = pronta per HR).
  - **A) Campagna avviata da HR/Formazione** (top-down, con scadenza
    opzionale): arriva ai responsabili di primo livello (radici dell'albero
    uffici); ognuno decide se rispondere direttamente per tutta la sua area o
    delegare ai propri sotto-responsabili, ricorsivamente fino alle foglie.
    Nella risalita, ogni responsabile che ha delegato vede le proposte di chi
    sta sotto e può approvarle/respingerle prima di passare il risultato al
    proprio responsabile, su su fino a HR.
  - **B) Richiesta spontanea** (bottom-up, senza campagna attiva): parte da
    un responsabile — qualunque livello, mai un utente finale — e sale per la
    stessa catena di approvazione fino a HR. Regola di partenza: qualsiasi
    responsabile può aprirne una (niente permesso granulare per gruppo per
    ora — si aggiunge solo se emerge un bisogno concreto).
  - Copre il tipo di evidenza che un audit ISO 9001 (cl. 7.2)/45001 chiede per
    dimostrare un processo di rilevazione dei bisogni formativi, non solo
    l'erogazione a valle.
  - Verificato con un test end-to-end su 4 livelli di gerarchia (delega →
    delega → risposta → approvazione → approvazione → coda HR, più un ramo
    rifiutato che si ferma e non risale) — tutti i passaggi di stato corretti.
  - Frontend: pagina responsabile "Fabbisogno formativo" (inviti da
    campagna con delega/risposta, richieste dei sotto-uffici da
    approvare/rifiutare, form richiesta spontanea, storico delle proprie
    richieste); pagina Ufficio Training per avviare/chiudere campagne e
    vedere la coda delle richieste pronte.
  - **Revisione del 13/10/2026 (v1.4.1)** dopo l'uso reale: gli inviti arrivano
    anche agli uffici creati dopo l'avvio della campagna; chi guida piu' uffici vede
    ogni campagna una volta con una riga per ufficio, che resta visibile con il suo
    stato (da decidere / inoltrata / risposta inviata); le due scelte "rispondo io" e
    "chiedo ai sotto-uffici" sono spiegate (la seconda compare solo se ci sono
    sotto-uffici); una risposta o richiesta spontanea contiene piu' esigenze (riga per
    argomento, periodo, riferimento, n. persone, note); il responsabile che e' anche
    Ufficio Formazione vede la voce. Menu: sezione "Fabbisogno formativo" con voce
    "Richieste"; "Le mie risorse" e' ora nella sezione "Il mio team".
  - **Vista della Formazione (v1.4.2)**: tre schede (Nuova campagna, Campagne,
    Richieste formative). Le richieste si guardano **per argomento** (varianti dello
    stesso argomento unite, persone indicate sommate, uffici, dettaglio a scomparsa) o in
    **elenco dettagliato**, con filtri (campagna o solo spontanee, ufficio con
    sotto-uffici, periodo, stato, testo), ordinamento dalle intestazioni e paginazione
    sul server, export. Campagne con avanzamento (uffici che hanno risposto, richieste).
    Stato finale lato responsabile: "Inviata (in carico alla Formazione)", lato
    Formazione "Ricevuta". Deciso con il committente di NON aggiungere un esito (accolta/non
    accolta) della Formazione: la campagna e' una raccolta, non un'approvazione.
  - **Fusione di richieste simili (v1.6.0)**: chi valuta le richieste dei sotto-uffici
    seleziona quelle sullo stesso tema e le unisce in una sola (argomento e nota
    riscritti, persone = somma modificabile). L'unione sale al posto delle originali, che
    restano intatte con stato "fusa" e un puntatore (`fusa_in_id`): a ogni livello e
    dopo piu' fusioni la provenienza (ufficio, autore, data, numeri, note) si ricostruisce
    con `GET /richieste/{id}/origine`. Si uniscono solo richieste della stessa campagna (o
    tutte spontanee) in attesa presso lo stesso ufficio. Tutela dei richiedenti: chi ha
    scritto una originale riceve una notifica, vede "Unita ad altre in..." e lo stato
    reale dell'unione (anche se rifiutata sopra, con il motivo); l'unione si annulla
    finche' nessuno sopra l'ha valutata. La Formazione conta le unioni una volta sola, con
    uffici e richieste originali; il filtro per ufficio guarda le originali. Audit
    `FABBISOGNO_UNIONE` e `FABBISOGNO_SCOMPOSIZIONE`. In piu': approva/rifiuta in blocco (con
    motivo), richieste raggruppate per argomento. Non fa: riconoscere da sola le richieste
    "simili" (le sceglie la persona).
  - Non ancora fatto, da considerare solo se emerge un bisogno concreto: la
    "fusione" di più richieste provenienti da sotto-uffici diversi in una
    sola prima di passarla al livello superiore (oggi si possono solo
    approvare/rifiutare singolarmente, o modificarne il contenuto in fase di
    approvazione).

### R. Autenticazione aziendale (SSO) — SPEDITO
- [x] **OpenID Connect, authorization code + PKCE**, configurato solo da
  ambiente (principio D2): `SSO_ISSUER`, `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`,
  `SSO_PUBLIC_URL` (base pubblica, serve a costruire il redirect URI
  `<SSO_PUBLIC_URL>/api/auth/sso/callback` da registrare nell'IdP),
  `SSO_LABEL`, `SSO_PROVISIONA_UTENTI`. Senza le quattro obbligatorie
  tutto resta com'e': solo email+password, nessun pulsante. Scelto OIDC
  generico (non solo Microsoft) perche' funziona con Entra (gia' usato per
  Teams: `SSO_ISSUER=https://login.microsoftonline.com/<tenant>/v2.0`,
  endpoint del tenant e non `/common`, serve un issuer concreto), Google
  Workspace, Keycloak e simili. Nessuna dipendenza nuova (`python-jose`,
  `httpx`).
- [x] **Flusso** (`api/sso.py`, `services/sso.py`): `GET /api/auth/sso/config`
  (pubblico, per mostrare il pulsante), `GET /login` (redirect all'IdP con
  `state`, `nonce`, PKCE S256), `GET /callback`. Verifica dell'id_token:
  firma RS256 dal JWKS dell'IdP (con un solo ricaricamento se la chiave e'
  ruotata), issuer, audience, scadenza, nonce; email da `email`/
  `preferred_username`/`upn`, rifiutata se `email_verified` e' falso.
  State/nonce/verifier viaggiano in un cookie HttpOnly firmato, SameSite=Lax,
  10 minuti, mai nell'URL. Il token dell'app torna al frontend nel fragment
  (`/login#sso_token=...`, mai inviato al server ne' nei log) e la pagina lo
  ripulisce dall'URL.
- [x] **Chi puo' entrare**: utente gia' presente, trovato per `sso_subject` o,
  al primo accesso, per email (case-insensitive); da li' conta il `sub`
  (`User.sso_subject`, unico): un'email riassegnata a un'altra persona non
  eredita l'account (`identita_diversa`). Al primo collegamento
  `origine_credenziali` passa da "locale" a "dominio". Utenti esterni
  esclusi (restano con password), disabilitati rifiutati. Utente sconosciuto:
  rifiutato di default; con `SSO_PROVISIONA_UTENTI=true` viene creato con
  ruolo "user" (e scattano i trigger dei percorsi, come per la creazione
  manuale). Nessun mapping automatico di ruoli/gruppi da claim: decisione
  rimandata, da riprendere se serve.
- [x] **Password con SSO attivo**: chi ha credenziali "dominio" non entra piu'
  con la password (`LOGIN_FAILED` nell'audit). **L'Admin tecnico resta sempre
  ammesso con password**, come accesso di emergenza se l'IdP e' giu'; gli
  utenti "locale" (es. esterni) non cambiano.
- [x] Audit: `LOGIN` con dettaglio "SSO" (e "primo collegamento SSO"),
  `SSO_LOGIN_FAILED` con il motivo (state non valido, token non valido,
  utente non abilitato, ...); la pagina Stato piattaforma mostra SSO attivo/
  non configurato e quanti utenti sono collegati. Pagina di login con errori
  leggibili per ogni caso.
- [x] **Verificato** con un IdP OIDC finto (chiavi RSA vere, discovery, JWKS,
  token endpoint con controllo PKCE) via TestClient: 29 controlli, tra cui
  id_token firmato con un'altra chiave, audience e nonce sbagliati, state
  manomesso, cookie assente, verifier PKCE errato, email non verificata o
  assente, utente sconosciuto/disabilitato/esterno, sub diverso su email gia'
  collegata, provisioning on/off, password rifiutata per "dominio" e ammessa
  per Admin tecnico. **Non testato contro un IdP reale** (servono le
  credenziali dell'app registrata): primo collaudo vero da fare quando
  il committente compila le variabili.

### S. Audit delle azioni dei discenti — SPEDITO
- [x] Eventi nuovi: `CHECKIN_INIZIO`/`CHECKIN_FINE` (check-in del discente),
  `REGISTRO_PRESENZE` (registro compilato dal docente, con quanti e chi),
  `TEST_TENTATIVO` (numero tentativo, punteggio, superato o no),
  `VIDEO_AVVIATO` e `VIDEO_COMPLETATO` (soglia 80%, la stessa che conta come
  completamento), e per lo staff `TEAMS_LINK`, `TEAMS_CREA_RIUNIONE`,
  `TEAMS_SINCRONIZZA_PRESENZE`, `TEAMS_REPORT_MANUALE`, `UPLOAD_EVIDENZA`.
- [x] **Video: solo avvio e completamento**, mai ogni heartbeat (arriva ogni
  pochi secondi e riempirebbe il registro); il completamento si registra
  una volta sola, al passaggio della soglia.
- [x] **Gradimento volutamente NON registrato**: e' anonimo per decisione
  gia' presa (vedi "Gradimento anonimo"); un evento con l'utente
  vanificherebbe l'anonimato.
- [x] Verificato via HTTP con JWT di un discente e di un docente: tutti gli
  eventi con utente, IP (da `CF-Connecting-IP`) e dettaglio corretti, video
  registrato due volte su otto heartbeat, nessun evento di gradimento, log
  backend senza errori, dati di test rimossi.

### T. Uniformità con altre piattaforme interne — SPEDITO
Confronto fatto con altre piattaforme interne (menu, impostazioni, About,
privacy, permessi), poi allineato per struttura, impostazioni e privacy utente.
- [x] **Decisione: ruoli fissi, niente permessi per gruppo.** Altre piattaforme usano permessi
  granulari per sezione/gruppo. Qui la piattaforma e'
  piatta (formazione/HR, docente, discente, responsabile): i permessi
  configurabili sarebbero complessita' senza valore. Scelta del committente.
- [x] **Informazioni** (`api/about.py`, `version.py`, pagina `/informazioni`,
  icona ⓘ nel footer della sidebar, per tutti): nome, azienda, versione
  (`APP_VERSION`, oggi 1.2.0) e novita'. L'Admin tecnico vede in piu' ambiente
  (Python, sistema, database, uptime), componenti con versione e stato delle
  integrazioni; gli altri utenti non vedono dettagli tecnici. **Da ricordare:
  a ogni rilascio aggiornare `APP_VERSION` e `CHANGELOG` in `api/about.py`.**
- [x] **Pagina Piattaforma** (`/piattaforma`, Impostazioni): nome della
  piattaforma (sidebar, login, titolo scheda, nome dell'app), URL pubblico,
  icona dell'app caricabile (precedenza: icona > logo aziendale > marchio
  predefinito), stato delle integrazioni in sola lettura (restano da ambiente,
  principio D2). Il **manifest PWA e' ora generato**
  (`GET /api/azienda/manifest.json`, `index.html` punta li') invece del file
  statico; `GET /api/azienda/pubblica` espone senza login solo nome/logo per
  la schermata di accesso. L'URL pubblico serve per i **link diretti nelle
  email** di notifica e comunicazione (`services/notifiche.con_link`) e per il
  link del feed calendario; senza URL le email restano come prima.
- [x] **Tema chiaro/scuro**: toggle nel brand della sidebar (🌙/☀️), scelta in
  `localStorage`, altrimenti segue il sistema; applicato prima del render per
  evitare il lampo di tema sbagliato.
- [x] **Campanella nella sidebar** (nel brand; nel footer a sidebar compressa),
  non piu' in cima alla pagina; il pannello si apre a destra della sidebar.
- [x] **Menu Amministrazione con sottomenu "Impostazioni"** (Azienda,
  Piattaforma, Stato piattaforma, Audit log, Informativa privacy), stato
  aperto/chiuso ricordato, a sidebar compressa le voci diventano icone.
- [x] **Impostazioni utente a schede**: Account, Password, Notifiche,
  Calendario, Privacy.
- [x] **Privacy** (`api/privacy.py`), ripensata: la piattaforma e' uno strumento
  aziendale e il trattamento non si basa sul consenso (formazione anche
  obbligatoria, registro da conservare), quindi **niente richiesta di
  cancellazione ne' anonimizzazione** (tolte, tabella `richieste_cancellazione`
  eliminata; la persona che lascia l'azienda si disattiva). Restano:
  - **Scarica i miei dati** (accesso/portabilita'): JSON con profilo,
    iscrizioni, evidenze, test, attestati, notifiche, attivita' registrata;
    **mai** credenziali, token o chiavi dei dispositivi; **il gradimento e'
    escluso** perche' anonimo.
  - **Informativa privacy** caricata dall'Admin tecnico (menu Impostazioni →
    Informativa privacy): testo e/o PDF (controllo della firma `%PDF-`, max
    15 MB), consultabile da ogni utente in Impostazioni → Privacy con data di
    aggiornamento, titolare e contatto presi dai dati azienda. **Nessuna
    accettazione al login**. Modifiche nell'audit log.
  - Da definire con il DPO: periodo di conservazione dopo la fine del rapporto;
    se fissato, aggiungere un'anonimizzazione manuale per gli utenti disattivati.
- [x] **Audit esportabile in Excel e PDF** oltre al CSV, con gli stessi filtri
  (`GET /api/admin/audit/export`, bottone Esporta standard; PDF limitato a
  2000 righe, Excel/CSV a 50.000).
- [x] **Drawer mobile**: sotto gli 800px la sidebar era nascosta senza alcun
  modo di aprirla (menu irraggiungibile da telefono). Ora c'e' una barra in
  alto con ☰, campanella e il menu a scomparsa con sfondo scuro; si chiude
  dopo la navigazione.
- [x] **Verificato**: API via HTTP (About per utente normale e admin, manifest,
  validazioni nome/URL, icona piccola/non valida/valida e uso nell'endpoint
  icona, export audit nei tre formati, 403 per non admin, la privacy) e **UI in un
  browser vero** (Playwright in container, 31 controlli: tema persistito,
  campanella e pannello, sottomenu, tutte le pagine nuove, schede, sidebar
  compressa, drawer mobile, nessun errore in console o rete) con controllo
  degli screenshot, da cui sono usciti e sono stati corretti troncamento del
  nome nel brand, sigla dell'icona e stile al passaggio del mouse. Dati di
  test rimossi.
- Rimasto fuori dal confronto: altre piattaforme hanno anche reset password, cambio
  password forzato e documenti legali con accettazione; non richiesti qui.

### U. Sicurezza degli accessi — SPEDITO (13/10/2026, v1.3.0)

Blocco, reset, cambio obbligatorio e policy password.
- [x] **Policy password unica** (`services/password_policy.py`): almeno 14 caratteri,
  una maiuscola, un numero, un carattere speciale; vale per setup, creazione utente,
  cambio, reset, modifica da admin e import CSV (le password generate sono conformi).
- [x] **Blocco account**: 5 tentativi falliti → 15 minuti (429), azione audit
  `ACCOUNT_BLOCCATO`; in piu' limite per indirizzo (30 login ogni 15 minuti, in
  memoria del processo). Lo sblocco avviene da solo o con un reset password.
- [x] **Sessioni legate alla password** (`users.token_version`, claim `tv` nel token):
  cambiare o reimpostare la password chiude le altre sessioni; chi ha fatto il cambio
  riceve un token nuovo. I token emessi prima della modifica restano validi finche'
  non si cambia password (tv assente = 0).
- [x] **Cambio password obbligatorio** (`password_da_cambiare`): dopo una password
  assegnata da un amministratore, creata in import o temporanea l'app mostra solo la
  schermata "Scegli la tua password". Non si applica agli utenti con credenziali di
  dominio.
- [x] **Password dimenticata**: risposta sempre identica (non rivela chi e'
  registrato), limite 10 richieste ogni 15 minuti per indirizzo. Con SMTP attivo e URL
  noto (URL pubblico o origine del browser) parte un link valido 2 ore, monouso, di cui
  nel DB resta solo l'hash. Senza SMTP la richiesta va all'Admin tecnico (pagina
  "Reset password", notifica in-app) che genera una password temporanea mostrata una
  sola volta. Gli utenti SSO non possono usarla.
- [x] **Audit**: `PASSWORD_CAMBIATA`, `PASSWORD_RESET_RICHIESTA/COMPLETATO/GENERATA`,
  `ACCOUNT_BLOCCATO`.
- [x] Verificato via HTTP (policy, blocco, sblocco, cambio, sessioni invalidate, reset
  con token valido/scaduto/riusato/falso, limite per IP) e in browser (schermata di
  cambio obbligatorio, pagine pubbliche). Il percorso con email non e' provato con un
  SMTP reale: il token e' stato inserito a mano nel DB.
- Nota: il blocco vale anche per l'Admin tecnico (si sblocca da solo dopo 15 minuti).

### V. Matrice formativa e pacchetto per l'ispezione — SPEDITO (13/10/2026, v1.3.0)

- [x] **Matrice formativa** (`GET /api/registro/matrice`, pagina in Ufficio Training):
  righe = persone (tutta l'azienda o un ufficio con i sotto-uffici), colonne = corsi
  richiesti dai percorsi attivi assegnati. Cella = stato migliore tra le iscrizioni:
  valido, in scadenza (entro 30 giorni), in corso, da aggiornare, scaduto, non
  completato, mancante (richiesto ma mai iniziato). Percentuale "in regola" sulle
  celle richieste; opzione per includere anche i corsi fatti ma non richiesti.
  Export CSV/Excel/PDF (A3 consigliato). Solo Ufficio Formazione e Admin tecnico.
- [x] **Pacchetto per l'ispezione** (`GET /api/registro/pacchetto-ispezione`, bottone
  nel Registro formazione): ZIP per azienda, ufficio, persona, corso o periodo con
  `LEGGIMI.txt`, registro (xlsx e pdf), matrice (xlsx, non per singola persona),
  attestati emessi, attestati esterni caricati e `indice_documenti.csv` con persona,
  corso e codice di verifica. Massimo 3000 documenti, PDF del registro fino a 2000
  righe. Ogni generazione e' nell'audit (`PACCHETTO_ISPEZIONE`).
- [x] Il registro ora si filtra e si esporta anche per persona.
- [x] **Fix mobile**: le tabelle larghe allargavano l'intera pagina su telefono; ora
  scorrono dentro il proprio riquadro.
- Limite noto: il "richiesto" deriva solo dai percorsi assegnati; un corso obbligatorio
  senza percorso compare solo se la persona lo ha iscritto.

### Z. Revisione del codice (14/10/2026, v1.7.2)

Revisione automatica del codice: dieci segnalazioni, tutte verificate sul codice.
- [x] **Corrette**: link di reset costruito dall'header Origin (ora solo URL configurato:
  Piattaforma o `SSO_PUBLIC_URL`; senza, la richiesta va all'Admin tecnico) e limite per
  email contro l'invio massivo; import dei cessati scelto esplicitamente (prima si attivava
  dal nome del file) e senza Admin tecnici; login e reset senza distinzione di maiuscole nelle
  email; SSO non collega per email un Admin tecnico; cambio password obbligatorio imposto anche
  dal server (con password assegnata si puo' solo cambiarla); feed calendario chiuso per chi e'
  disattivato; elenco dei responsabili/sottoposti/uffici guidati solo per se' e per la Formazione.
- [x] **Blocco dopo 5 tentativi** (deciso: soluzione piu' sicura): risposta identica per password
  sbagliata, email inesistente e account sospeso (stesso messaggio, stesso codice, tempi pareggiati
  con un controllo fittizio), niente piu' 429 per account; la sospensione dura 15 minuti, si toglie
  con "Password dimenticata" e viene segnalata agli Admin tecnici (una notifica all'ora per account)
  e nell'audit. Resta inevitabile che chi conosce un'email possa sospenderla per 15 minuti.
- [x] **Limiti per IP e audit** (v1.8.0): l'IP del client non si prende piu' da header scritti dal
  client. Il nginx della piattaforma imposta sempre `X-Real-IP` con chi si connette davvero; il
  backend crede a `CF-Connecting-IP` e a `X-Forwarded-For` solo se quell'indirizzo e' un proxy
  dichiarato in `PROXY_FIDUCIARI` (env, reti separate da virgola; vuoto = nessun proxy fidato). La
  catena forwarded si legge da destra fermandosi al primo indirizzo non fidato. In azienda basta
  indicare l'indirizzo con cui il proxy aziendale arriva alla piattaforma. Nel server domestico
  `PROXY_FIDUCIARI=172.16.0.0/12` (tunnel Cloudflare dal gateway Docker): verificato che una
  richiesta dalla LAN con header falsi registra il proprio IP.
- [x] **Migrazioni vere** (v1.8.0): Alembic (`backend/migrations`, `alembic.ini`). All'avvio
  `app/migrazioni.py` prende un blocco del database (advisory lock) e: database vuoto -> applica
  0001 e successive; database precedente alle migrazioni -> lo porta allo stato di partenza
  (`schema_legacy.py`, usato una volta sola) lo marca 0001 e applica il resto; altrimenti applica
  le mancanti. Il database di sviluppo e' stato marcato 0001 senza perdere nulla (dump di
  sicurezza prima). **Regola**: ogni cambio ai modelli richiede una migrazione
  (`alembic revision --autogenerate -m "..."` dal container del backend); un test confronta modelli
  e migrazioni e fallisce se manca. I test costruiscono il database dalle migrazioni.
- [x] **Password dei nuovi utenti** (v1.8.0): creazione manuale e import CSV mandano un link
  monouso di 3 giorni per scegliere la password (stesso meccanismo del reset), mai la password.
  La password iniziale nel form e' facoltativa; senza canale email (SMTP + URL pubblico)
  l'admin vede una temporanea una sola volta; gli utenti del dominio non ricevono inviti.

### Z2. Seconda revisione del codice (14/10/2026, v1.8.1)

Dieci segnalazioni verificate, nove corrette: limite di login per IP che contava anche gli accessi
riusciti (ora solo i fallimenti); annullamento di iscrizioni gia' completate e promozioni dalla
lista d'attesa senza posto libero (corretto anche nell'offboarding); disattivazione dal modulo
utente che non liberava iscrizioni, dispositivi e calendario; riconoscimento delle persone di
Entra solo per un indirizzo (ora mail, UPN e alias); `at_hash` che avrebbe bloccato l'SSO con
Google/Keycloak/Okta; variabili SMTP vuote che facevano fallire l'avvio; a capo nell'oggetto delle
email; chiavi dei limiti mai scartate; email inviate dentro la richiesta di login. Resta, come
deciso, la sospensione a tempo di un account: chiunque conosca un'email puo' sospenderla per
15 minuti (segnalato agli Admin tecnici e nell'audit).

### Z3. Terza revisione del codice (14/10/2026, v1.8.2)

Dieci segnalazioni, nove corrette e una chiarita: giri nella gerarchia dei gruppi (controllo al
salvataggio + visite protette); CF-Connecting-IP creduto da qualsiasi proxy fidato (ora solo con
`PROXY_CLOUDFLARE=true`); docenti che perdevano le risposte corrette salvando un test (e il
salvataggio di un test con opzioni andava in errore: trovato scrivendo il test); pianifica senza
controlli sullo stato e con inviti doppi; email/push sincroni e prima del commit (ora in
sottofondo e solo dopo il commit); logo non verificato e icona che poteva andare in errore;
iscrizioni oltre la capienza (anche per un conteggio dei posti che non vedeva le iscrizioni appena
create nella stessa richiesta) e in sessioni chiuse; promossi senza invito dopo una disattivazione;
lista d'attesa ferma quando aumentano i posti. Chiarita: il "motivo dell'obbligo" dei percorsi
non si salva piu' per scelta (l'obbligo e' del corso), il frontend non lo manda piu'.


### Z4. Quarta revisione del codice (14/10/2026, v1.8.3)
Otto correzioni su dieci segnalazioni verificate: ruolo dell'ultimo Admin tecnico, auto-iscrizione in sessioni non aperte, invii email in sottofondo (reset password, inviti CSV), formule CSV/Excel, test del docente, freno Entra su installazioni piccole, importazione configurazione (gruppi di sistema, campi assenti), messaggio di login errato. Il blocco account dopo 5 tentativi resta (temporaneo, risposta uniforme, avviso agli Admin tecnici): è il compromesso accettato.


### Z5. Rilievi di CodeRabbit sulla cronologia pubblica (v1.8.4 e seguenti)
La cronologia è stata pubblicata a fasi (PR #1-#8) e ogni fase recensita da CodeRabbit. I rilievi, verificati sul codice attuale, sono in `docs/rilievi-coderabbit.md` e si correggono in quattro blocchi: 1.8.4 sicurezza e integrità dei dati (fatto: file caricati non più pubblici, SSO, reset password, vincoli contro le corse, piano Entra legato all'anteprima), 1.8.5 correttezza e prestazioni del backend (fatto: rinnovo, validazione degli ingressi, esportazioni, pacchetto ispezione, invii, calendario, push), 1.8.6 interfaccia (fatto: errori mostrati, tastiera, risposte vecchie scartate, banner), 1.8.7 documenti (fatti tutti e quattro: serie chiusa). Aperto, da decidere: i video in `/videos` sono ancora serviti senza accesso (servirebbero indirizzi firmati a tempo).

### Y. Etichette dei corsi — SPEDITO (14/10/2026, v1.7.0)

Ragionata con il committente: una sola categoria per corso non basta (un corso di sicurezza
informatica e' insieme "Cybersecurity" e "Trasversale"), ma tag liberi diventano caos e
mescolano dimensioni diverse. Soluzione: etichette in **famiglie**.
- [x] Famiglie definite dall'Ufficio Formazione (pagina "Etichette dei corsi"): nome,
  descrizione, scelta singola o multipla, obbligatoria; etichette che si scelgono da un
  elenco (mai digitate), si rinominano ovunque, si **archiviano** se in uso (restano nelle
  estrazioni e sui corsi che le avevano, non si assegnano piu'), si eliminano solo se mai
  usate, si **uniscono** (doppioni). Un'etichetta "esclusiva" (es. Trasversale) fa
  comparire un avviso, non un blocco, se scelta con altre della stessa famiglia.
- [x] (dalla 2.4.0 non più predefinite: si definiscono da zero) Famiglie iniziali: Tematica, Riferimento normativo (il filtro degli audit), Ambito
  (Trasversale / clienti), Obbligo (legge, cliente, policy interna, facoltativo; scelta
  singola). Il vecchio campo Categoria e' migrato in Tematica.
- [x] **Decisione del committente**: l'obbligo e' una proprieta' del corso, il percorso e'
  un'iniziativa organizzativa. Tolto "motivo dell'obbligo" dai percorsi (il dato resta nel
  database con il valore predefinito, nessuna nota da perdere). L'ambito cliente sta sul
  corso, non sulla sessione.
- [x] Filtri per etichetta (stessa famiglia = una qualsiasi, famiglie diverse = tutte):
  tabella corsi, registro formazione ed export, matrice formativa ed export, pacchetto
  per l'ispezione (il filtro compare nel LEGGIMI). Le etichette sono una colonna degli
  export e viaggiano con la configurazione.
- Limite noto: le estrazioni usano le etichette di oggi, non quelle che il corso aveva al
  momento dell'erogazione. Da riprendere solo se un audit lo richiede.
- [x] (v1.7.1) Filtro per etichetta anche in Dashboard KPI e relativi export, Dashboard
  Ufficio Formazione (indicatori, persone con problemi, scoperture dei percorsi, sessioni
  imminenti) e nelle sessioni, che mostrano le etichette del corso. Resta fuori solo
  il confronto tra versioni di un corso (e' gia' su un corso solo).

### X. Configurazione esportabile/importabile — SPEDITO (14/10/2026, v1.6.0)

Non e' un backup (quello e' dell'infrastruttura IT): serve a portare la configurazione da
sviluppo a produzione, a ricostruirla dopo un errore o ad avviare un'altra istanza.
- [x] Pagina "Configurazione" (Impostazioni, solo Admin tecnico): scarica un file JSON
  (`formato`, `schema`, versione app) con dati aziendali e impostazioni della piattaforma
  (nome, URL, testo dell'informativa privacy), gruppi e uffici con gerarchia e responsabili
  (per email), societa' di formazione, corsi (con rinnovo automatico) e percorsi (passi,
  prerequisiti, gruppo di assegnazione automatica).
- [x] Importazione con **anteprima obbligatoria**: calcola cosa verrebbe creato e aggiornato
  (campo per campo) lavorando davvero e poi annullando, quindi l'anteprima coincide con il
  risultato (verificato nei test). Riconosce per nome (corsi, percorsi, societa') o per
  percorso (gruppi), **aggiunge e aggiorna, non cancella mai**, non tocca le versioni dei
  corsi esistenti. Riferimenti mancanti (responsabile, gruppo, corso) diventano avvisi.
  Rifiuta file di altri formati o di una versione piu' recente. Audit `CONFIG_EXPORT` e
  `CONFIG_IMPORT`.
- [x] **Fuori dal file, da valutare dopo** (decisione del committente): video, immagini e loghi,
  template degli attestati, test e domande, ruoli di sistema; mai inclusi: persone,
  iscrizioni, credenziali e chiavi (SMTP, SSO, Graph, push).
- [x] Esportazione in CSV/Excel/PDF di utenti, gruppi, societa' di formazione, catalogo corsi
  e percorsi (stesso bottone Esporta, anche nelle rispettive pagine). Un import di dati
  oltre agli utenti (CSV esistente) non e' previsto.
