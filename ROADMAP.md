# Roadmap — Piattaforma E-Learning

Documento vivo, non un piano deciso: va aggiornato/riordinato insieme al committente man
mano che si converge sulle priorità. Ultimo aggiornamento: 2026-10-13 (dopo sincronizzazione utenti e test automatici).

> Le sezioni già spedite e i verbali delle revisioni del codice sono in [`docs/roadmap-archivio.md`](docs/roadmap-archivio.md), spostate senza modifiche per tenere qui solo ciò che è aperto, parcheggiato o deciso e ancora da fare.

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
  o a un Docente che ha effettivamente insegnato quel corso (docente di
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

### Z6. Sicurezza per l'uso aziendale (verso la 2.0.0)
Obiettivo: superare controlli di sicurezza (SAST, analisi delle dipendenze) e proteggere i dati degli utenti. Quattro passi, ciascuno una release:
- [x] **1.9.0 Video e CORS** — i video non sono più una cartella pubblica: ogni riproduzione passa da un indirizzo a tempo (2 ore, legato al video) richiesto da chi ha diritto (iscritto alla sessione, Ufficio Formazione, Admin). CORS chiuso di default (`CORS_ORIGINS` solo da ambiente, mai `*`): funziona su qualsiasi indirizzo. Upload video e sottotitoli scritti a pezzi con limite. Tolti dalla documentazione i riferimenti a strumenti e progetti specifici del committente: la piattaforma è generica.
- [x] **1.9.1 Registro attività** — due livelli (importanti / tutti), conservazione `AUDIT_RETENZIONE_MESI` (24 mesi, da ambiente), riepilogo per periodo, indici; esportazione giornaliera in file NDJSON (`AUDIT_EXPORT_DIR`) e copia in tempo reale sull'output (`AUDIT_LOG_STDOUT`) per un sistema di gestione dei log. Da verificare in produzione con un collettore reale.
- [x] **1.9.2 Pagina Info** — agli utenti (e all'Ufficio Formazione) solo nome, azienda e versione; changelog e dettagli tecnici solo all'Admin tecnico. Da riprendere con il committente per eventuali altri contenuti della pagina.
- [x] **1.9.3 Cifratura dei file e dei segreti** — file in `uploads` cifrati (AES-256-GCM a blocchi), chiave VAPID cifrata, token del calendario solo come impronta, strumento `app.cifratura_cli`, `docs/sicurezza.md`.
- [x] **1.9.4 Video cifrati e più qualità** — 480p/720p/1080p/4K fino alla qualità dell'originale (`VIDEO_ALTEZZE`), scelta automatica o manuale nel player, file cifrati a blocchi con lettura a intervalli, originale eliminato dopo la conversione. Non fatto: streaming adattivo (HLS) che cambia qualità da solo durante la visione; i tempi di conversione del 4K sono da misurare sull'hardware di produzione.
- [x] **1.9.5 Dipendenze, immagini e controlli** — PyJWT al posto di python-jose, sito servito da nginx senza privilegi, `package-lock.json`, immagini senza vulnerabilità alte/critiche, `scripts/controlli-sicurezza.sh` e CI su GitHub (test, Bandit, pip-audit, npm audit, Trivy). Da provare la prima esecuzione su GitHub.
- [x] **1.9.6 Da Create React App a Vite** — compilazione con Vite 8, `npm audit` completo a zero vulnerabilità e reso bloccante in CI e script; file con interfaccia in `.jsx`; provate tutte le pagine in un browser vero.
- [x] **1.9.7 Cifratura dei dati personali nel database** — nome/email utenti, dati degli enti esterni, email/IP/dettaglio del registro cifrati nella colonna; impronte (HMAC) per login, unicità e filtri esatti; conversione dei dati esistenti con `cifratura_cli cifra`; ordinamento per nome nel programma.
- [x] **2.0.0 Pronta per l'uso aziendale** — chiusura della serie: nessuna funzione nuova; versione, changelog e documenti allineati, suite completa e controlli di sicurezza verdi. Restano a carico di chi installa HTTPS, cifratura del disco, backup e custodia della chiave (vedi `docs/sicurezza.md`).

### Z7. Utenti, ruoli e gruppi (dopo la 2.0.0)
Obiettivo: separare chi è una persona (anagrafica), che cosa fa nella formazione (ruoli come tag) e dove sta (gruppi = uffici). Tre passi, ciascuno una release:
- [x] **2.1.0 Pagina Utenti a schede** — schede Elenco / Nuovo utente / Importa CSV; elenco con ricerca, filtri, ordinamento sulle intestazioni e paginazione; tolto «Esporta» dai Gruppi.
- [x] **2.2.0 Permessi, uffici e mansioni** — il ruolo unico diventa tre interruttori (Admin, Formazione, Docente) che si sommano; i gruppi sono solo uffici (uno per persona, obbligatorio per gli interni non Admin); mansioni come etichette trasversali (assegnazione percorsi e filtri); docenti scelti solo tra Docenti ed esterni; esterni mai iscritti come discenti; pagina Ruoli e gruppi di sistema eliminati; progetto in `docs/progetto-ruoli-mansioni.md`.
- [x] **2.12.1 Copertine dei corsi** — ogni corso può avere una copertina (la Formazione la carica dalla scheda del corso); senza immagine un riquadro colorato generato dal titolo con l'icona del tipo di corso; compare nella Home, nel Catalogo, nella pagina del corso e nell'elenco dei corsi.
- [x] **2.12.0 Spazi di lavoro** — il menu si divide in «La mia formazione», «Gestione» e «Amministrazione», ognuno con le sue voci raggruppate; selettore con i numeri delle cose da fare, passaggio automatico allo spazio giusto dai collegamenti, ultimo spazio ricordato; nuova pagina «Da gestire» per la Formazione, Riepilogo dell'amministrazione, Home del discente con «Continua da dove eri»; notifiche che portano alla pagina; barra in basso sul telefono.
- [x] **2.11.0 Un nome per ogni cosa** — glossario applicato a menu, titoli e messaggi (Formazione, Panoramica, Indicatori, Registro attività, Modelli di attestato, Richieste di corsi, Fabbisogno del mio ufficio, Richieste di nuova password, Storico e attestati; «sessione» al posto di «edizione»); stati e modalità sempre con la loro etichetta; icone a linea al posto delle emoji; pagina della sessione con titolo del corso, stato e «Esporta»; conferme nella finestra della piattaforma.
- [x] **2.10.0 Percorsi che iscrivono** — i percorsi hanno una modalità (libero / sequenziale / con propedeuticità scelte con una selezione); si assegnano a delle persone dalla pagina Percorsi (ricerca, filtri, elenco di chi li ha con lo stato di ogni corso, «Togli»); assegnando, la persona viene iscritta ai corsi sbloccati e a mano a mano ai successivi, scegliendo la sessione (video sempre disponibile, poi la più vicina con posti); se non c'è una sessione si aspetta e si viene iscritti alla pubblicazione; i corsi bloccati non si anticipano; la Formazione può spostare una persona su un'altra sessione.
- [x] **2.9.0 Come si accede e quando è disponibile** — iscrizione da soli: no / liberamente / con approvazione del responsabile (o della Formazione se non ne ha uno) / con approvazione della Formazione; un video con data si apre dall'ora (fino alla fine, se c'è) e si completa da solo come i sempre disponibili; sessioni finite segnalate «da chiudere»; chiusura senza doppi attestati.
- [x] **2.8.0 Questionari di gradimento personalizzabili** — la Formazione definisce le domande aggiuntive (stelle, sì/no, scelta, testo libero) in questionari con nome, uno predefinito e uno scelto da ogni corso; il modulo si compila da un link «Compila il test di gradimento» che apre una finestra; risposte nei report e nel CSV; la scelta di chi può iscriversi a un corso è più chiara («aperto a tutti» / «i responsabili iscrivono il team»).
- [x] **2.7.4 Il video al centro** — nella pagina del corso il video è grande e protagonista, con le informazioni sotto; nel Catalogo i corsi già completati vanno in fondo; «Il tuo parere sul corso» al posto di «Com'è andata?»; Pillow 13 (vulnerabilità corrette).
- [x] **2.7.3 Storico corsi e attestati** — storico a colonne (corso, modalità, data, durata, esito, emesso il, codice verifica) con «Visualizza» nel browser e «Scarica PDF»; l'attestato si scarica con un nome parlante `Corso_Cognome_Nome_Data.pdf`.
- [x] **2.7.2 Seguire un corso e gestirlo sono due cose** — la pagina della sessione ha due viste: per chi segue il corso solo ciò che serve a seguirlo (video, test, presenza, attestato), per chi la gestisce gli strumenti di gestione; nessuno vede più chi altro è iscritto, salvo Formazione e docenti della sessione; corretto il video che ripartiva da capo dopo 2 secondi.
- [x] **2.7.1 Eliminare i corsi, pubblicare le sessioni** — eliminazione definitiva di un corso (solo admin tecnico, solo se senza tracce di formazione, con titolo da riscrivere); sessioni in bozza da «Pubblicare» (e riportare in bozza se vuote), «Pubblica subito» alla creazione; il check-in personale solo a chi è iscritto.
- [x] **2.7.0 Catalogo e corsi sempre disponibili** — pagina «Catalogo» per tutti con i corsi a cui ci si iscrive da soli (sessioni in programma e corsi video sempre disponibili); sessioni video «sempre aperte» senza date, con completamento e attestato in automatico; pulsante per pianificare una sessione (prima non c'era nell'interfaccia).
- [x] **2.6.0 Il mio team e corsi chiusi o aperti** — «Il mio team» a quattro schede (albero degli uffici, formazione del team per sessione o per persona, corsi disponibili, richieste e approvazioni) al posto della vecchia pagina che mostrava tutte le sessioni; corsi chiusi (predefinito) / aperti ai responsabili in modo diretto o su richiesta; richieste di iscrizione approvate dalla Formazione con notifiche.
- [x] **2.5.0 Durata dei corsi e sessioni riorganizzate** — durata nel corso, ereditata e forzabile nella sessione, congelata alla chiusura, sull'attestato e nei report (assorbe «ore dichiarate»); sessioni a schede con tabella ricca e filtri; docenti e discenti separati con ricerca e filtri per ufficio e mansione.
- [x] **2.4.1 Sezione Video a schede** — elenco con tabella e pannello sotto la riga (titolo, anti-skip, anteprima, sottotitoli, capitoli in m:ss modificabili); eliminazione di un video solo se non usato.
- [x] **2.4.0 Etichette libere, corsi a schede, player compatto** — nessuna famiglia di etichette preimpostata (si parte da zero); pagina Corsi a schede con modulo di modifica sotto la riga; player video compatto; nella pagina della sessione chi la gestisce vede il video collegato con un'anteprima a richiesta, non il player. Segue la 2.4.1 con la sezione Video a schede.
- [x] **2.3.4 Ruoli a colpo d'occhio** — capsule colorate per i ruoli nell'elenco utenti (Admin, Formazione, Docente, Esterno, Utente) con legenda; «Formatore» rinominato «Docente» ovunque; file `.coderabbit.yaml` che spegne l'avviso sulle docstring.
- [x] **2.3.3 Importazione da Excel con controllo prima** — file .xlsx oltre al CSV, anteprima con riepilogo per persona e conferma, uffici/mansioni mancanti non scartano la riga (persona creata senza, con avviso), modelli Excel e CSV generati dal sistema, filtro «Senza ufficio».
- [x] **2.3.2 Selettore colore e modifica sotto la riga** — selettore colore leggibile con esadecimale e colori pronti; modulo di modifica sotto la riga (uffici, mansioni, utenti); spiegazione di cosa fa il CSV con uffici e mansioni inesistenti.
- [x] **2.3.1 Uffici più facili da gestire** — modifica completa degli uffici (colore, gerarchia, stato), elenchi in ordine alfabetico con percorso intero, modelli CSV scaricabili; corretto il filtro uffici di 5 pagine.
- [x] **2.3.0 Nome e Cognome** — due campi separati (cifrati), mostrati e ordinabili (cognome, poi nome); import CSV con `nome` e `cognome`; accesso aziendale ed Entra usano nome e cognome dell'azienda, altrimenti dividono il nome intero (la regola è approssimata: i dati esistenti vanno controllati).

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
