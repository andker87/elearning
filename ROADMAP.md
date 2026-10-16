# Roadmap — Piattaforma E-Learning

Documento vivo, non un piano deciso: va aggiornato/riordinato insieme al committente man
mano che si converge sulle priorità. Ultimo aggiornamento: 2026-10-13 (dopo sincronizzazione utenti e test automatici).

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
- **Dashboard per persona**: Utente (i miei corsi / storico), Formatore (le mie
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

## Ancora aperto (riepilogo al 2026-10-13, v1.5.0)

**Da collaudare con sistemi reali** (costruiti e testati solo con simulatori): SSO con un
account Entra vero, sincronizzazione utenti con Entra ID (sempre prima l'anteprima), link
di reset password e notifiche con un SMTP vero.

**In coda**: valutazione dell'efficacia (da disegnare insieme), mappatura reparti Entra →
gruppi e uffici (dopo il collaudo), (la fusione delle richieste di fabbisogno e' stata fatta, v1.6.0).

**Da valutare per la configurazione**: includere video, immagini e loghi, template degli attestati, test e domande nell'esportazione.

**Parcheggiate**: firma digitale degli attestati (prima va scelto il certificato), matrice
delle competenze (da ragionare), SCORM/xAPI/H5P (non servono per i video prodotti in
casa), promemoria Teams/Slack (priorita' bassa), multi-tenant, assistenza AI nella
piattaforma, backup e ripristino (con la produzione).

**Scartate o chiuse**: cancellazione dei dati, Accordo Stato-Regioni 2025, esito della
Formazione sulle richieste di fabbisogno, tracciamento offline, permessi per gruppo,
gamification.

## Decisioni di dettaglio prese — SPEDITE

- [x] **Test di apprendimento**: creazione riservata a Ufficio Formazione/Admin
  o a un Formatore che ha effettivamente insegnato quel corso (docente di
  almeno un'edizione) — mai generati dall'assistente. La reportistica per-
  docente resta una query derivata (`TentativoTest` → `Iscrizione` →
  `Edizione` → `EdizioneDocente`, nessun campo duplicato), costruita quando
  si arriva alla dashboard KPI.
- [x] **Test pre/post**: facoltativi (nessun vincolo cambiato: un corso può
  già avere 0+ test di qualunque momento). Aggiunto `Corso.confronta_pre_post_test`
  — l'Ufficio Formazione decide corso per corso se attivare il confronto
  pre/post; il calcolo del delta vero e proprio è rimandato alla dashboard
  KPI (stessa dipendenza del punto sopra).
- [x] **Gradimento anonimo con target distinti**: `Gradimento` ora ha
  `voto_corso`/`commento_corso` + una riga `GradimentoDocente` per ciascun
  docente dell'edizione (voto 1-5, validato contro i docenti reali
  dell'edizione). Vista admin (`GET /edizioni/{id}/gradimenti`) e CSV
  riscritte: mai più il nome di chi ha risposto, solo medie/distribuzioni e
  commenti spaiati dall'autore. Migrazione dati: i vecchi `voto`/`commento`
  vengono copiati su `voto_corso`/`commento_corso` allo startup, poi le
  colonne vecchie vengono eliminate.

## In sospeso dalla sessione precedente

- [x] Dashboard/flusso operativo dedicato **Ufficio Formazione** — SPEDITO
  (`api/dashboard_formazione.py`, pagina "Dashboard" in cima alla sezione
  Ufficio Training, prima voce). Card KPI cliccabili (compliance %, scaduti,
  da aggiornare, non completati, in scadenza nei prossimi 30gg, persone mai
  partite su un percorso assegnato, sessioni nei prossimi 14gg) con filtro
  per ufficio/reparto (scende nei sotto-uffici) e per corso; grafico a barre
  dei problemi aperti per categoria (Recharts, nuova dipendenza frontend);
  tabella persone con, per ogni problema, azioni dirette "Iscrivi" (apre il
  picker di edizioni aperte per quel corso) e "Sollecita" (notifica in-app +
  email immediata, `POST /api/dashboard/formazione/sollecito` - non passa
  dal dedup dello scheduler, un sollecito manuale deve poter essere ripetuto
  a piacere); blocco sessioni imminenti con posti liberi/lista d'attesa;
  export CSV (riusa il registro formazione, sezione A). La "scopertura"
  (corsi mai nemmeno iniziati, distinta da scaduto/da aggiornare/non
  completato) è derivata dai Percorsi formativi assegnati e non completati,
  guardando quali step sono sbloccati ma non fatti.
- [x] **SPEDITO** — Dashboard/flusso **Admin tecnico**: due pagine in
  "Amministrazione" (solo Admin tecnico), disegnate con il committente ridimensionando
  la proposta iniziale (meno "KPI da vetrina", più salute vera):
  - **Stato piattaforma** (`GET /api/admin/salute`): utenti distinti con login
    nelle ultime 24h/7gg e login falliti 24h (derivati dall'audit log, nessun
    campo nuovo); scheduler (attivo, prossima esecuzione, ultimo giro + esito
    + storico, traceback se fallito); SMTP solo badge configurato/non
    configurato (niente contatori invii); spazio disco
    del volume video, dimensione video/upload, video in errore di
    transcodifica, dimensione DB.
  - **Tracciamento scheduler**: tabella `job_runs` scritta da
    `services/job_tracking.esegui_tracciato` (il job notifiche ora passa da
    li'); l'APScheduler vive in memoria e prima non lasciava traccia di un
    giro fallito o saltato al riavvio. Un'eccezione viene registrata e non
    ferma lo scheduler. Lo storico parte dal primo giro dopo il deploy.
  - **Audit log** (`GET /api/admin/audit`, `/audit/filtri`, `/audit/export.csv`):
    filtri per testo libero (nome/dettaglio/id/utente), azione, tipo entita',
    utente, IP, intervallo date; paginazione, riga espandibile con tutti gli
    ID, export CSV (max 50k righe) con gli stessi filtri.
  - **Copertura audit estesa**: prima solo 7 punti (login, utenti, import CSV,
    modifica corso). Ora anche: corsi (create/update/delete/nuova versione),
    gruppi, organizzazioni, azienda (dati, logo, test SMTP), sessioni
    (crea/modifica/pianifica/chiudi/duplica, docenti, iscrizioni,
    annullamenti con eventuale promozione da lista d'attesa, comunicazioni),
    auto-iscrizione (richiesta/approva/rifiuta), percorsi (crea/modifica/
    assegna/sincronizza), template attestati, richieste corso, campagne
    fabbisogno, rigenerazione token calendario. NON coperti qui:
    modifiche video/test e push subscribe (basso valore ispettivo). Le azioni
    dei discenti sono state aggiunte dopo, vedi sezione S.
  - **IP reale nell'audit**: dietro tunnel Cloudflare l'IP del socket era
    sempre quello del container nginx. Ora `services/audit.ip_client` legge
    `CF-Connecting-IP`, poi `X-Forwarded-For`, poi `X-Real-IP`. Caveat: gli
    header sono falsificabili da chi raggiunge nginx direttamente (porta
    2018) senza passare dal tunnel - ok come informazione, non come prova.
  - Verificato: job tracciato ok + errore (traceback salvato, nessuna
    eccezione rilanciata); HTTP via nginx con JWT: 403 per utente normale,
    401 senza token, tutti i filtri e la paginazione, CSV, IP simulato da
    `CF-Connecting-IP`; giro completo corso/sessione/docenti/iscrizione/
    comunicazione/annulla/duplica/chiusura/percorso/template/token
    calendario con 19 eventi audit corretti; log backend senza errori;
    frontend compilato senza warning; dati di test rimossi (zero residui,
    audit tornato alle righe originali).
- [x] Dashboard KPI/report aggregati (per corso, per docente, per reparto) —
  SPEDITO, vedi sezione F (`api/dashboard_kpi.py`, pagina "Dashboard KPI").

## Proposte di feature (da ricerca di mercato + riflessione)

Ho guardato come si posizionano Docebo e altri LMS enterprise/compliance nel 2026.
Punto di partenza, non un elenco da spuntare tutto: alcune cose contano molto per
un contesto di compliance come il tuo, altre sono più "nice to have" da piattaforme
generaliste e potrebbero non valere lo sforzo.

### A. Irrobustire il lato compliance (il vero differenziale)
- [x] **Escalation al responsabile** — SPEDITA: `scadenza_corso` e `ripeti_corso`
  (le due notifiche di scadenza vera, non i promemoria generici di percorso/
  edizione imminente) ora notificano anche il/i responsabile(i) derivati dalla
  gerarchia uffici (sezione L), non solo il discente. Stesso meccanismo di
  dedup degli altri tipi di notifica, nessun modello nuovo.
- [x] **Registro formazione aggregato esportabile** — SPEDITO
  (`api/registro.py`, pagina "Registro formazione" sotto Ufficio Training).
  Una riga per ogni (persona, corso) con almeno un'iscrizione non annullata,
  filtrabile per reparto (scende nei sotto-uffici via
  `services/gerarchia.persone_ufficio_e_sottouffici`, nuova) e per intervallo
  di data completamento. Stato compliance derivato: `valido` (completato,
  entro la validità se il corso ne ha una), `scaduto` (validità superata),
  `non_completato`, `in_corso` (iscritto/in lista d'attesa). Export
  `GET /api/registro/export.csv`. Nota: filtra sulla data di completamento,
  non sulla data di scadenza — "cosa scade in questo periodo" resta coperto
  dalle notifiche (sezione A/D), non da questo report.
- [x] **Versionamento dei contenuti** — SPEDITO. Decisione del committente: mai un
  bump automatico su una modifica qualsiasi del corso (con 500+ utenti
  l'impatto sarebbe troppo pesante da scatenare per sbaglio) - è un'azione a
  parte, esplicita, corso per corso: "Nuova versione" nella pagina Corsi, con
  una spunta "Richiedi a chi lo ha già fatto di ripeterlo":
  - **spuntata** (corsi su base normativa, dove l'aggiornamento conta
    davvero): chi ha completato una versione precedente non è più compliant
    (appare "da aggiornare" nel registro e nel proprio storico) e riceve una
    notifica (+ escalation al responsabile, stesso meccanismo della sezione
    A);
  - **non spuntata** (default - es. induction aziendale, dove non serve
    rifare tutto ad ogni piccola modifica): chi l'ha già completato resta
    compliant, vede solo un'etichetta informativa "aggiornamento disponibile",
    nessuna notifica.
  Modello: `Corso.versione` (incrementato ad ogni bump) e
  `Corso.versione_minima_valida` (alzata solo se si richiede la ripetizione);
  `Iscrizione.versione_corso` registra con quale versione la persona ha
  completato. Il PUT normale di un corso non tocca questi campi (non sono
  nemmeno nel payload) - solo `POST /api/corsi/{id}/nuova-versione` lo fa.
- [ ] Firma digitale reale sugli attestati (già previsto come opzione pluggable,
  da attivare quando/se serve).

### A2. Template grafici per gli attestati
- [x] **Editor drag-and-drop stile "stampa unione"** — SPEDITO. Richiesta di
  il committente dopo aver visto come un'altra piattaforma interna genera i voucher premio (immagine
  di sfondo + testo sovrapposto): qui serviva poter scegliere *quali* campi
  mostrare e *dove*, non solo un logo fisso. Modello `CertificatoTemplate`
  (`models/certificato_template.py`): nome, immagine di sfondo caricata
  (PNG/JPG/WEBP, dimensioni lette con Pillow), `campi` (JSON: lista di
  `{chiave, x, y, font_size, bold, align, colore}` in pixel dell'immagine
  originale), `is_default`. **Più template possono coesistere** (richiesta
  esplicita del committente, es. un layout per corsi interni e uno per corsi
  erogati da enti esterni): ogni `Corso` può assegnarne uno
  (`certificato_template_id`, selettore nella pagina Corsi); se non
  assegnato si usa quello con `is_default`; se nessuno esiste si ricade sul
  layout fisso ReportLab di prima (ora con logo, sezione G2).
  Pagina "Template attestati" (sotto Ufficio Training): lista template a
  sinistra, a destra l'editor — canvas con lo sfondo in scala, palette dei
  campi disponibili (vocabolario fisso: nome partecipante, titolo corso,
  data, monte ore, azienda, ente erogatore, docente/i, codice di verifica),
  trascinabili col mouse direttamente sull'immagine (drag via mouse events,
  nessuna libreria aggiunta); un pannello per campo regola dimensione,
  allineamento, colore, grassetto. Bottone **"Anteprima PDF"** che genera un
  attestato di prova con valori segnaposto (`GET
  /api/certificato-templates/{id}/anteprima.pdf`) — fondamentale per
  verificare l'allineamento esatto, non solo l'anteprima a schermo. La
  generazione vera (`services/certificati.py`, `genera_pdf_da_template`)
  dimensiona la pagina PDF sull'aspect ratio reale dell'immagine (non A4
  fisso) e converte le coordinate pixel→punti in base alla larghezza/altezza
  originali. Il codice di verifica univoco anti-contraffazione
  (`Certificato.codice_verifica`, endpoint pubblico `/certificati/verifica/
  {codice}`) esisteva già da prima di questa sessione — nessun lavoro nuovo
  lì, resta disponibile anche come campo posizionabile nel template.

### B. Matrice delle competenze (diverso da "ha fatto il corso")
- [ ] Un **training matrix** (chi ha completato cosa, già coperto) è diverso da
  una **skills matrix** (livello di competenza reale su un'attività, con
  eventuale valutazione del responsabile/osservazione pratica). Se vi serve
  tracciare competenze e non solo corsi, è un modello dati a parte da discutere.

### C. Interoperabilità contenuti (gap pratico probabile)
- [ ] **Import di pacchetti SCORM/xAPI già pronti**: se qualcuno in azienda ha già
  contenuti autorati con Articulate/iSpring/altro, oggi la piattaforma accetta
  solo video nativi caricati da voi — niente import di corsi SCORM esistenti.
  Vale la pena solo se avete già contenuti di questo tipo in giro.

### D. Notifiche multicanale
- [x] **Email (SMTP)** — SPEDITO, poi **migrato a configurazione solo da
  ambiente** (decisione del committente sul principio sys admin/platform admin,
  vedi sezione "Profili" più sotto): `SMTP_HOST/PORT/USER/PASSWORD/MITTENTE/TLS`
  si impostano solo come variabili d'ambiente (`.env`/docker-compose, vedi
  `config.py` — stesso schema già usato per Microsoft Graph), mai da UI. La
  pagina "Azienda" mostra solo lo stato read-only (configurato/host/mittente/
  sicurezza) con un bottone "Invia prova" (`POST /api/azienda/smtp/test`), ma
  nessun campo editabile: chi amministra la piattaforma da UI (Admin tecnico)
  vede, non modifica. Le vecchie colonne `azienda.smtp_*` (contenevano la
  password in chiaro) sono state rimosse dal DB all'avvio. `services/email.py`
  (`invia_email`, ora senza parametro `db`) resta l'unico punto di invio,
  agganciato in `services/notifiche.py` su ogni notifica generata dallo
  scheduler, oltre che sulle comunicazioni/annunci manuali su sessione
  (sez. M) e sulle notifiche push (sez. E).
- [ ] Eventuale integrazione Teams/Slack per promemoria.

### D2. Profili: sys admin vs platform admin (principio architetturale)
- [x] **SMTP come caso pilota** — SPEDITO (vedi sopra). Deciso con il committente dopo
  un confronto con altre piattaforme interne: in nessuna
  esiste un *ruolo* "sys admin" separato nel modello utenti/permessi — è un
  principio su **dove vivono i segreti**, non un livello di permesso in più.
  Regola adottata anche qui: configurazione di infrastruttura (credenziali
  SMTP, e in futuro un'eventuale SSO aziendale) vive solo in env/container,
  mai nel DB, mai editabile da nessuna UI applicativa; chi amministra la
  piattaforma (Admin tecnico oggi) ne vede solo lo stato. L'SSO aziendale
  (sezione R) segue lo stesso schema: tutto da variabili d'ambiente.

### E. Mobile / offline
- [x] **PWA installabile + notifiche push** — SPEDITO. Scope deciso con
  il committente: installabile su pc/cellulare/tablet con notifiche push, **non**
  funzionamento offline (quello resta fuori, vedi nota xAPI sotto se servirà
  in futuro). `public/manifest.json` (nome, icone, `display: standalone`,
  `theme_color` sul verde-smeraldo della piattaforma) + `public/
  service-worker.js` minimale: nessuna cache/offline, solo passthrough di
  rete (per l'installabilità) e gestione `push`/`notificationclick`. Icone
  generate al volo da `GET /api/azienda/icona` (endpoint pubblico, serve
  anche al manifest): usa il logo azienda se caricato, altrimenti lo stesso
  marchio "EL" della sidebar.
  **Push**: RFC 8292 (Web Push + VAPID) via `pywebpush`/`py-vapid`. Le
  chiavi VAPID le genera la piattaforma stessa al primo avvio
  (`Azienda.vapid_private_key/vapid_public_key`) — a differenza di SMTP non
  sono credenziali di terze parti fornite da chi amministra il server, quindi
  restano nel DB invece che in ambiente (non contraddice il principio della
  sezione D2). Modello `PushSubscription` (una riga per dispositivo/browser,
  endpoint unico — un utente può averne più d'una). `api/push.py`:
  `GET /public-key`, `POST /subscribe`, `POST /unsubscribe`, `GET /stato`.
  `services/push.py` (`invia_push`) agganciato agli stessi due punti
  dell'email (sezione D): `_crea_se_assente` per tutte le notifiche
  scheduler e il sollecito manuale della dashboard Ufficio Formazione; una
  sottoscrizione scaduta/revocata (404/410 dal servizio push del browser)
  viene rimossa automaticamente al primo tentativo fallito, mai un errore
  visibile all'utente. Toggle "Attiva/disattiva notifiche push" in
  Impostazioni utente (`src/push.js`: richiesta permesso browser,
  sottoscrizione `PushManager`, invio al backend), più due banner proattivi
  mostrati in cima a ogni pagina (`components/InstallPwaBanner.js`,
  `components/NotificationPermissionBanner.js`, stile barra sottile
  "mini-banner" — icona + una riga di testo + pulsante compatto + chiusura,
  dismissibili e mai più riproposti dopo la chiusura): il primo cattura
  `beforeinstallprompt` a livello di modulo (`src/pwaInstall.js`, registrato
  prima del mount di React per non perdere l'evento) e propone "Installa"
  quando il browser lo offre, con istruzioni manuali su iOS (che non
  supporta quell'evento); il secondo propone di attivare le notifiche se il
  permesso del browser è ancora "default". Pattern comune ad altre piattaforme interne. Sidebar diventata anche collassabile (icone sole,
  64px) e ridimensionabile a trascinamento (180–360px, doppio click per
  ripristinare), preferenze per device in `localStorage` — stesso pattern di
  `Layout.jsx`/`Layout.js` di altre piattaforme interne (`components/Shell.js`).
  **Verificato**: generazione chiavi VAPID, round-trip da PEM salvato,
  invio reale a un endpoint FCM (fallisce correttamente con 410 su un
  endpoint finto, pulizia automatica confermata), manifest/service-worker/
  icona serviti correttamente da nginx, build di produzione senza errori.
  **Non verificabile da qui**: l'installazione vera su un dispositivo e la
  ricezione reale di una notifica richiedono un browser vero.
  **Nota operativa — risolta**: i service worker richiedono un contesto
  sicuro (HTTPS), eccetto su `localhost`. la piattaforma può stare dietro
  un tunnel o proxy HTTPS (la configurazione resta a carico di chi installa): nginx continua a esporre tutto in chiaro, il proxy
  termina l'HTTPS davanti — nessuna modifica necessaria in questo repo.
  Resta da fare solo il test reale su dispositivo (banner di installazione,
  notifica push).
- [ ] Tracciamento offline vero (xAPI) per chi non ha una postazione fissa
  (operai, venditori in giro) — fuori scope per ora, il committente ha chiesto solo
  installabilità + push.

### F. Reportistica/KPI (già segnata come "in sospeso" sopra)
- [x] Dashboard aggregate per ufficio formazione — SPEDITO, vedi sezione "In
  sospeso dalla sessione precedente" sopra.
- [x] Dashboard **KPI per corso/docente/periodo** — SPEDITO
  (`api/dashboard_kpi.py`, pagina "Dashboard KPI" sotto Ufficio Training).
  Filtri comuni (corso, docente, ufficio/reparto, periodo) e 5 viste a tab,
  ciascuna con grafico (Recharts) + tabella + export CSV:
  - **Per corso** e **Per docente**: confronto a barre su una metrica
    scelta (tasso completamento, punteggio test, gradimento corso/docenti,
    ore erogate);
  - **Andamento nel tempo**: stesse metriche raggruppate per mese di
    svolgimento (grafico a linee) - per vedere un trend, non uno snapshot;
  - **Confronto edizioni**: richiede un corso selezionato, una riga per
    edizione con la versione del contenuto dominante tra chi l'ha
    completata (sezione versionamento);
  - **Confronto versioni**: richiede un corso selezionato, aggrega solo chi
    ha completato per versione del contenuto (punteggio test e gradimento
    medi) - il confronto "prima/dopo" un aggiornamento normativo.
  Punteggio test: media dell'ultimo tentativo per iscrizione (non la media
  di tutti i tentativi, per non penalizzare chi ha dovuto riprovare).
  "Ore erogate" è una stima quando non dichiarate esplicitamente (durata
  data_inizio/data_fine), dichiarata come tale in UI - non un dato certo per
  le modalità diverse da "esterna". Aggiunta `recharts` come dipendenza
  frontend (condivisa con la dashboard operativa, sezione precedente).
- [x] **Export multi-formato (CSV/Excel/PDF A4-A3)** — SPEDITO
  (`services/export.py`, punto unico riusato da registro formazione e
  dashboard KPI). CSV com'era, **Excel** via `openpyxl` (intestazione in
  grassetto, larghezza colonne auto), **PDF** via ReportLab (`Table`/
  `TableStyle`, intestazione ripetuta su ogni pagina, **formato A4 o A3**
  selezionabile, orientamento landscape, logo azienda in testa se impostato
  — sezione G2). Endpoint unificati: `GET /api/registro/export` e
  `GET /api/dashboard/kpi/export` ora accettano `formato=csv|xlsx|pdf` e
  `pagina=A4|A3` (prima erano CSV-only su `/export.csv`). Componente
  frontend riusabile `ExportButton` (menu a tendina coi 4 formati) sostituito
  a ogni vecchio bottone "Esporta CSV" in Registro formazione, Dashboard
  Ufficio Formazione e tutte e 5 le viste della Dashboard KPI (prima
  "Confronto versioni" non aveva export, ora ce l'ha anche lei). Nessuna
  gestione permessi separata per l'export: chi vede il dato a schermo può
  anche esportarlo (scelta del committente, niente permesso dedicato
  per ora).

### G. Import/export massivo
- [x] **Import CSV utenti per onboarding bulk** — SPEDITO, poi arricchito
   `POST
  /api/auth/users/import-csv` (solo Admin tecnico, pagina Utenti), accetta
  `,` o `;` come separatore. Colonne: `email`, `full_name`/`nome` (obbligatorie),
  `password` (opzionale, altrimenti generata), `role`, `is_external`,
  `organizzazione` (ragione sociale esatta, match per nome), `gruppi` (nomi
  separati da `;` **o `|`**, match per nome — i nomi non trovati sono
  segnalati ma non bloccano la riga), `data_ingresso` (AAAA-MM-GG). Ogni riga
  è indipendente: email duplicata, ruolo/organizzazione non valida o data
  malformata producono un errore solo su quella riga, le altre proseguono.
  Se SMTP è configurato (sez. D) la password generata viene mandata via
  email all'utente, altrimenti torna nella risposta/tabella a video per
  comunicarla a mano. **Modalità "cessati"** (stesso schema di
  come in altre piattaforme interne): se il nome del file contiene "cessat" (es.
  `cessati_settembre.csv`), lo stesso endpoint disattiva in blocco per email
  invece di creare — basta la colonna `email`, lo storico formativo resta
  intatto (l'account smette solo di essere attivo).

### G2. Logo azienda
- [x] **Upload e uso del logo** — SPEDITO. Il campo `Azienda.logo_path`
  esisteva già nel modello ma non era mai stato collegato a nulla; ora
  `POST /api/azienda/logo` (PNG/JPG/WEBP, solo Admin tecnico, sostituisce
  il file precedente) e `DELETE /api/azienda/logo`, servito da
  `/uploads/azienda/logo.*`. Usato in due punti: stampato in testa agli
  attestati generati col layout di riserva (`services/certificati.py`,
  quando il corso non ha un template grafico assegnato — vedi sezione A2) e
  in testa a ogni esportazione PDF (`services/export.py`, sezione F).

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

### J. Assistenza AI (trend 2026, es. "Harmony" di Docebo)
- [ ] Generazione automatica di domande del quiz a partire dal contenuto del
  corso/video.
- [ ] Trascrizione/sottotitoli automatici dei video (oggi si caricano a mano).
- [ ] Ricerca assistita nel catalogo corsi.

### K. Multi-tenant / white-label
- [ ] Resta un orizzonte futuro (come discusso nel KICKOFF) — il modello dati è
  già pensato per non ostacolarlo, non richiede lavoro ora.

### L. Gerarchia aziendale / responsabili (fondamenta per più feature) — DISEGNO CONCORDATO
- [ ] Niente entità nuova: l'"ufficio" è un `Group` esistente con un flag
  `is_ufficio` (per non confonderlo con gli altri gruppi liberi usati per il
  rolling massivo), gerarchia già data dal `parent_id` che hanno già.
- [ ] **Un solo responsabile per ufficio** (campo singolo `responsabile_id` su
  `Group`, niente co-gestione — confermato dal committente).
- [ ] **Il responsabile di una persona è derivato, non un campo suo**: è il
  responsabile del gruppo-ufficio di cui è *membro*. Se quella persona è a sua
  volta responsabile di un (sotto-)ufficio, il suo responsabile è il
  responsabile del gruppo **padre** di quello che dirige — non deve essere
  iscritta come membro lì. Esempio verificato con il committente: Back Office (resp.
  Alberto) ha due assistenti come membri diretti (resp. = Alberto) e due
  sotto-uffici, Bancario (resp. Daniele) e Assicurativo (resp. Sara), entrambi
  con padre Back Office → il responsabile di Daniele e Sara è Alberto, senza
  che siano membri di Back Office. L'escalation/reportistica aggregata
  cammina sull'albero (query ricorsiva), non è un dato duplicato.
- [ ] **Una persona può appartenere a più gruppi-ufficio insieme** (es.
  part-time su due aree) → in quel caso ha più responsabili validi in
  parallelo, equivalenti, nessun "principale" da scegliere (reportistica la
  conta in entrambi i reparti; per iscriverla a un corso basta uno qualsiasi
  dei due responsabili).
- [ ] **Sotto-responsabili equivalenti tra loro** quando approvano/filtrano
  richieste che risalgono la catena (nessun ordine titolare/supplente).
- [ ] `User.manager_id` (già nel modello ma mai letto da nessuna parte) va
  **rimosso**: era un secondo campo che poteva discordare dal responsabile
  derivato dal gruppo, fonte di casino evitabile — una sola fonte di verità.
  `User.can_see_all` resta: è un concetto diverso (visibilità totale
  indipendente dalla gerarchia, es. ufficio formazione), non in conflitto.
- [x] Abilita insieme: l'escalation delle scadenze al responsabile — SPEDITA,
  vedi sezione A. L'iscrizione delle proprie risorse ai corsi da parte dei
  responsabili — SPEDITA: `POST /edizioni/{id}/iscrizioni` ora accetta anche
  un responsabile (non solo Ufficio Formazione), ma solo per i propri
  sottoposti (derivati da `sottoposti_di`, 403 altrimenti); lato frontend,
  sidebar con sezione "Responsabile" → "Le mie risorse" quando
  `sottoposti_di` non è vuoto, e un blocco dedicato nella pagina sessione per
  iscrivere una risorsa (lista già filtrata ai propri sottoposti, non la
  lista utenti intera che vede l'Ufficio Formazione). La richiesta di una
  sessione formativa con pre-iscrizione — SPEDITA: modello `RichiestaCorso`
  (corso a catalogo o nuovo argomento, note, persone pre-iscritte tra i propri
  sottoposti), single-hop diretta a HR (niente cascata, a differenza del
  fabbisogno formativo sotto). Pagina responsabile "Richiedi un corso" e
  pagina Ufficio Training "Richieste corso" per approvare/rifiutare. Il
  sondaggio di fabbisogno formativo — SPEDITO, vedi sezione Q.

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
`PROXY_CLOUDFLARE=true`); formatori che perdevano le risposte corrette salvando un test (e il
salvataggio di un test con opzioni andava in errore: trovato scrivendo il test); pianifica senza
controlli sullo stato e con inviti doppi; email/push sincroni e prima del commit (ora in
sottofondo e solo dopo il commit); logo non verificato e icona che poteva andare in errore;
iscrizioni oltre la capienza (anche per un conteggio dei posti che non vedeva le iscrizioni appena
create nella stessa richiesta) e in sessioni chiuse; promossi senza invito dopo una disattivazione;
lista d'attesa ferma quando aumentano i posti. Chiarita: il "motivo dell'obbligo" dei percorsi
non si salva piu' per scelta (l'obbligo e' del corso), il frontend non lo manda piu'.


### Z4. Quarta revisione del codice (14/10/2026, v1.8.3)
Otto correzioni su dieci segnalazioni verificate: ruolo dell'ultimo Admin tecnico, auto-iscrizione in sessioni non aperte, invii email in sottofondo (reset password, inviti CSV), formule CSV/Excel, test del formatore, freno Entra su installazioni piccole, importazione configurazione (gruppi di sistema, campi assenti), messaggio di login errato. Il blocco account dopo 5 tentativi resta (temporaneo, risposta uniforme, avviso agli Admin tecnici): è il compromesso accettato.


### Z5. Rilievi di CodeRabbit sulla cronologia pubblica (v1.8.4 e seguenti)
La cronologia è stata pubblicata a fasi (PR #1-#8) e ogni fase recensita da CodeRabbit. I rilievi, verificati sul codice attuale, sono in `docs/rilievi-coderabbit.md` e si correggono in quattro blocchi: 1.8.4 sicurezza e integrità dei dati (fatto: file caricati non più pubblici, SSO, reset password, vincoli contro le corse, piano Entra legato all'anteprima), 1.8.5 correttezza e prestazioni del backend (fatto: rinnovo, validazione degli ingressi, esportazioni, pacchetto ispezione, invii, calendario, push), 1.8.6 interfaccia (fatto: errori mostrati, tastiera, risposte vecchie scartate, banner), 1.8.7 documenti (fatti tutti e quattro: serie chiusa). Aperto, da decidere: i video in `/videos` sono ancora serviti senza accesso (servirebbero indirizzi firmati a tempo).

### Z6. Sicurezza per l'uso aziendale (verso la 2.0.0)
Obiettivo: superare controlli di sicurezza (SAST, analisi delle dipendenze) e proteggere i dati degli utenti. Quattro passi, ciascuno una release:
- [x] **1.9.0 Video e CORS** — i video non sono più una cartella pubblica: ogni riproduzione passa da un indirizzo a tempo (2 ore, legato al video) richiesto da chi ha diritto (iscritto alla sessione, Ufficio Formazione, Admin). CORS chiuso di default (`CORS_ORIGINS` solo da ambiente, mai `*`): funziona su qualsiasi indirizzo. Upload video e sottotitoli scritti a pezzi con limite. Tolti dalla documentazione i riferimenti a strumenti e progetti specifici del committente: la piattaforma è generica.
- [x] **1.9.1 Registro attività** — due livelli (importanti / tutti), conservazione `AUDIT_RETENZIONE_MESI` (24 mesi, da ambiente), riepilogo per periodo, indici; esportazione giornaliera in file NDJSON (`AUDIT_EXPORT_DIR`) e copia in tempo reale sull'output (`AUDIT_LOG_STDOUT`) per un sistema di gestione dei log. Da verificare in produzione con un collettore reale.
- [x] **1.9.2 Pagina Info** — agli utenti (e all'Ufficio Formazione) solo nome, azienda e versione; changelog e dettagli tecnici solo all'Admin tecnico. Da riprendere con il committente per eventuali altri contenuti della pagina.
- [ ] **1.9.3 Cifratura dei dati** — file e campi sensibili cifrati con chiave da ambiente; documento di sicurezza (disco, backup, trasporto).
- [ ] Controlli automatici di sicurezza del codice (Bandit, pip-audit/npm audit, Semgrep, Trivy) e poi **2.0.0**.

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
- [x] Famiglie iniziali: Tematica, Riferimento normativo (il filtro degli audit), Ambito
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

### W. Decisioni e idee emerse dal recheck del 13/10/2026

Backup: ambiente di sviluppo, dati sacrificabili — nessuna azione (da riprendere
con la produzione: i volumi Docker con nome non sono visti dal backup dei file).

- [x] **Offboarding / sincronizzazione utenti da Entra ID** — SPEDITO (13/10/2026, v1.4.0).
  Configurazione solo da ambiente (`ENTRA_SYNC_GRUPPO_ID`, `ENTRA_SYNC_AUTO`, credenziali
  `GRAPH_*` con permessi applicativi `User.Read.All` e `GroupMember.Read.All`).
  - Il gruppo Entra definisce chi usa la piattaforma. Pagina "Sincronizzazione utenti"
    (Amministrazione): **anteprima** delle modifiche, poi applica. Il piano propone:
    creare chi manca, aggiornare il nome, **disattivare** chi non e' piu' nel gruppo o ha
    l'account disabilitato, riattivare chi e' tornato (solo su richiesta).
  - Mai toccati: utenti esterni, Admin tecnici, utenti di domini diversi da quelli del
    gruppo. La data di ingresso (che fa scattare i percorsi "ingresso in azienda") si
    imposta solo per assunzioni degli ultimi 60 giorni, cosi' il primo import non
    assegna l'onboarding a tutto il personale.
  - **Disattivazione completa** (`services/offboarding.py`, usata anche dall'import CSV
    dei cessati): chiude l'account e le sessioni aperte, annulla le iscrizioni a sessioni
    non chiuse promuovendo chi era in lista d'attesa, toglie i dispositivi push; lo
    storico formativo resta. Docenze aperte e responsabilita' di ufficio non bloccano:
    vengono segnalate da riassegnare (notifica a Admin tecnico e Ufficio Formazione).
  - **Giro notturno opzionale** (02:30, tracciato in `job_runs`, visibile in Stato
    piattaforma): applica creazioni, nomi e disattivazioni, mai le riattivazioni. **Freno
    di sicurezza**: se le disattivazioni superano il 20% degli utenti in ambito (minimo 5)
    o le creazioni 200, non fa nulla e avvisa.
  - Audit per ogni utente toccato (`CREATE`, `UPDATE`, `DISATTIVA_UTENTE`) e riepilogo
    `SYNC_ENTRA`.
  - **Non provato con un tenant Entra reale**: testato con Graph simulato. Primo vero
    collaudo quando ci sono le credenziali: fare sempre prima l'anteprima.
  - Non incluso, possibile passo successivo: mappare reparto/gruppi Entra sui gruppi e
    uffici della piattaforma.
- [x] **Test automatici** — SPEDITO (13/10/2026, v1.4.0): 108 test in `backend/tests`,
  lanciabili con `docker compose --profile test run --rm tests`. Usano un database
  separato (`<nome>_test`, creato al volo, mai quello vero) e un SSO finto con chiavi
  RSA vere. Coprono accessi (policy, blocco, sessioni, reset), permessi per ruolo con
  tabella endpoint x ruolo, stati del registro e matrice, lista d'attesa, SSO (compresi
  gli attacchi), informativa/export privacy, audit e filtri, pacchetto ispezione,
  sincronizzazione ed offboarding. Verificato che falliscono se si rompe una regola
  (soglia di blocco, scadenze, policy password). Non coprono ancora il frontend.
- [x] **Rinnovo automatico, opzionale** — SPEDITO (13/10/2026, v1.5.0). Opzione per
  corso (spunta in creazione e nella tabella dei corsi, spenta di default, solo se il corso
  ha una validita'; giorni di anticipo, default 30). Giro notturno alle 02:00 (tracciato
  in `job_runs`): chi ha l'ultimo completamento in scadenza o scaduto e non e' gia'
  iscritto viene iscritto alla prossima sessione pianificata non passata (le sessioni
  senza data, tipiche dei videocorsi, hanno la precedenza), saltando quelle piene senza
  lista d'attesa; con lista d'attesa va in lista. Avvisi a persona e responsabile; senza
  sessioni avviso alla Formazione una volta a settimana per corso. Audit
  `RINNOVO_AUTOMATICO`. Anteprima "chi verrebbe iscritto" dalla tabella corsi.
  Non copre: aggiornamenti di versione del corso, persone mai iscritte.
- [ ] **Valutazione dell'efficacia** a distanza (es. 90 giorni, compilata dal
  responsabile): livello successivo a gradimento e test.
- [ ] **Promemoria su Teams/Slack, opzionali**: attivabili e configurati da
  ambiente come le altre integrazioni (principio D2); l'email resta il canale base.
- [ ] **SCORM / xAPI / H5P**: oggi i videocorsi sono prodotti internamente; da
  riprendere se si producono o si comprano contenuti in questi formati.
- [ ] **Firma digitale degli attestati**: nel modello esiste solo il tipo
  `firmato` (`TipoCertificato`), senza provider ne' codice di firma. Disegno proposto
  (da confermare): come SMTP e SSO, la si configura **solo da ambiente** dal sys admin
  (certificato o provider di firma remota, marca temporale), la piattaforma esegue una
  firma di prova e mostra "configurata e funzionante" (e i giorni alla scadenza del
  certificato); solo allora l'Ufficio Formazione puo' attivare la spunta "firma gli
  attestati". Serve prima decidere che certificato usare (sigillo aziendale, firma di
  una persona, provider).
- [x] **Accordo Stato-Regioni 2025 (n. 59/CSR)** — CHIUSO, non applicabile. Decisione
  del committente: la piattaforma non eroga la formazione D.Lgs 81/08 (la erogano societa'
  accreditate, che decidono modalita' e strumenti): qui si rendiconta soltanto. Nessuna
  funzione da costruire; restano utili registro, attestati esterni e matrice.
- **Decisioni del 13/10/2026 (committente)**: promemoria Teams/Slack a priorita' bassa;
  multi-tenant parcheggiato; matrice delle competenze da ragionare bene prima di
  impostarla (rischio di costruire qualcosa senza senso: partire da un caso d'uso
  concreto, non da un modello); tracciamento offline scartato.
- **Videocorsi**: non serve SCORM; i video si caricano come MP4 nel player esistente (capitoli, sottotitoli, anti-skip). Come produrli è a discrezione di chi gestisce i corsi.
- Assistenza AI (quiz generati, sottotitoli automatici): resta parcheggiata.

## Idee scartate

- **Tracciamento offline / lavoro senza rete** (E): scartato dal committente il 13/10/2026,
  non ne vede l'utilita'.

- **Gamification** (punti/badge/leaderboard): valutata e scartata — non adatta
  al tono di un contesto di formazione obbligatoria/compliance italiana.

## Fonti consultate

- [LMS compliance 2026 (Coggno)](https://coggno.com/blog/must-have-features-compliance-lms-2026/)
- [Come scegliere un LMS per la compliance (Vector Solutions)](https://www.vectorsolutions.com/resources/blogs/how-to-choose-an-lms-for-compliance-training/)
- [Gestire la formazione sulla sicurezza (PuntoSicuro)](https://www.puntosicuro.it/pubbliredazionale-C-119/gestire-la-formazione-sulla-sicurezza-in-modo-efficace-conforme-AR-25222/)
- [Docebo Review 2026: Pricing, Features, and Fit](https://lmspedia.org/docebo-review/)
- [Best Corporate Learning Management Systems (LMS) of 2026 — Docebo](https://www.docebo.com/learning-network/blog/corporate-learning-management-systems/)
- [LMS for Compliance Training: The Complete 2026 Guide + Evaluation Checklist](https://trainery.ai/blog/lms-for-compliance-training)
- [The Ultimate Guide to Training Matrix Software in 2026](https://www.compono.com/articles/training-matrix-software-guide-2026)
- [Competency-Based LMS: Top Features to Look for in 2026](https://www.skillscaravan.com/post/competency-based-lms)
- [xAPI vs SCORM: Choosing the Right eLearning Standard](https://www.ispringsolutions.com/blog/xapi-vs-scorm)
- [SCORM Compliant LMS, xAPI & cmi5 — TalentLMS](https://www.talentlms.com/features/scorm-lms)
