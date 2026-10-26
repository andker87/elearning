# Rilievi di CodeRabbit da trattare (registro)

Registro unico dei commenti di CodeRabbit sulle PR della cronologia. Ogni rilievo è stato letto contro il codice **attuale** (1.8.3, non contro lo stato della fase recensita).
Le correzioni si fanno in quattro blocchi (PR): **1.8.4** sicurezza e integrità dati, **1.8.5** correttezza e prestazioni backend, **1.8.6** interfaccia, **1.8.7** documenti e rifiniture. Le PR di fase si fondono senza ritocchi.

Stato: `DA FARE` fondato · `VERIFICARE` probabile, da guardare nel codice prima · `CHIUSO` già a posto (con motivo) · `FATTO 1.8.x` corretto nella versione indicata.

## PR #1 — fase 1.0.0

| Stato | File | Rilievo |
|---|---|---|
| CHIUSO | services/certificati.py | "Critical: i chiamanti passano il titolo, non Corso": falso, passano l'oggetto Corso |
| CHIUSO | api/calendario.py | `calendar_token` su User e migrazione: già presenti |
| CHIUSO | frontend Azienda.js | blocco `smtp` in GET /azienda: già presente |
| CHIUSO | services/export.py | formule CSV/XLSX: corretto nella 1.8.3 |
| FATTO 1.8.4 | api/autoiscrizione.py, services/iscrizioni.py | corsa (TOCTOU) su auto-iscrizione e capienza: serializzare controllo e inserimento, vincolo di unicità (utente, edizione) |
| FATTO 1.8.4 | api/gradimenti.py | doppio gradimento in parallelo: unicità su `gradimenti.iscrizione_id` + gestione IntegrityError (400) |
| FATTO 1.8.4 | models/fabbisogno.py | unicità su (campagna_id, ufficio_id) |
| FATTO 1.8.4 | models/richiesta_corso.py | unicità su `richieste_corso_persone` |
| FATTO 1.8.5 | api/certificato_templates.py | validare immagine e template_id prima di scrivere file; validare forma di `campi`; file temporaneo unico per l'anteprima |
| FATTO 1.8.5 | api/dashboard_kpi.py | ordinamento che fallisce se solo alcune sessioni hanno `data_inizio` |
| FATTO 1.8.6 | frontend/public/service-worker.js | validare l'URL della notifica (stessa origine) prima di aprirlo |
| FATTO 1.8.6 | frontend Gradimento.js | stelle non usabili da tastiera; passare i docenti della sessione al modulo — i docenti erano già passati dalla pagina della sessione (verificato) |
| FATTO 1.8.5 | requirements.txt | Pillow 11.0.0 → versione più recente (verificare che esista la 12.3.0 indicata) |
| FATTO 1.8.5 | services/calendario.py | `_escape` non gestisce il ritorno a capo `\r` |
| FATTO 1.8.5 | services/email.py | ripulire `allegato_nome` nell'header Content-Disposition; gestire `submit` fallito nel hook after_commit |
| FATTO 1.8.5 | api/calendario.py | token calendario salvato in chiaro (consigliato: hash + confronto a tempo costante); query per sessione in un'unica query — token in chiaro: lasciato così (l’indirizzo del calendario va rimostrato all’utente, come ogni calendario in abbonamento; si rigenera da Impostazioni); le query sono ora due |
| FATTO 1.8.5 | api/richieste_corso.py | bloccare nuova valutazione di richieste già decise; validare `persone_ids` e `corso_id` (UUID), rifiutare `argomento` vuoto; N+1 in `_serialize` |
| FATTO 1.8.5 | api/fabbisogno.py | rifiutare deleghe e risposte a campagna chiusa; `_Contesto` carica tutto a ogni chiamata |
| FATTO 1.8.5 | api/dashboard_formazione.py | ambiti ufficio e senza filtro contano popolazioni diverse; commit della notifica prima di email e push |
| FATTO 1.8.4 | api/autoiscrizione.py | gestire sessione mancante in `approva` (già coperto in 1.8.3 per lo stato; verificare il caso 404) |
| CHIUSO | api/gradimenti.py | validare `docente_id` e intervallo dei voti; query per docente/riga — validazione di docente e voti già presente; query dei nomi accorpate (1.8.5) |
| FATTO 1.8.5 | services/certificati.py | valori di campo non validi in `genera_pdf_da_template` |
| FATTO 1.8.5 | services/push.py, api/push.py | `print` per i fallimenti; `invia_push` blocca la richiesta e fa commit a metà; corsa su `endpoint` nella sottoscrizione; `py-vapid` mancante dai requirements |
| FATTO 1.8.6 | frontend (varie) | gestione errori: SessioniResponsabile, RichiesteCorsoAdmin, RichiestaCorso, DashboardFormazione (sollecito), Azienda (rimuoviLogo), TemplateAttestati; banner PWA e notifiche che si nascondono dopo un fallimento; `push.js` annullamento a metà; stale closure in TemplateAttestati |

## PR #2 — fase 1.1.0

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | services/sso.py | collega l'account usando `preferred_username`/`upn` se manca `email`: richiedere un'email verificata (rilievo più importante) |
| FATTO 1.8.5 | api/admin_tecnico.py | esportazione audit troncata in silenzio (50.000 righe CSV/Excel, 2.000 PDF): renderlo esplicito; ordinamento con spareggio unico; filtro "fine" che aggiunge un giorno a un datetime; salute senza storage che fallisce |
| FATTO 1.8.5 | api/auth.py | import CSV in `async def` che blocca il server: usare un handler sincrono |
| FATTO 1.8.5 | api/azienda.py | icona pubblica senza limiti di elaborazione; decodificare l'icona prima di sostituire il file esistente |
| CHIUSO | api/azienda.py | nuovi campi della società nel mapping `Azienda` — il modello di ingresso comprende già tutti i campi della società (verificato) |
| CHIUSO | api/evidenze.py | presenza Teams e relativo audit nello stesso commit — link e audit sono nello stesso commit (verificato) |
| CHIUSO | api/test.py | domande conservate per tentativi già in corso — i tentativi salvano le risposte solo alla consegna: nessun tentativo in corso da proteggere (verificato) |
| FATTO 1.8.5 | api/video.py | soglia di completamento (80%) uguale a quella dell'evento di audit — soglia unica, definita in api/evidenze.py e usata anche da api/video.py |
| FATTO 1.8.6 | frontend AuditLog.js | richieste vecchie che sostituiscono i risultati attuali; dettagli non accessibili da tastiera |
| CHIUSO | frontend Login.js | token SSO in `localStorage` (valutare alternativa) — il token resta in localStorage come per l’accesso normale (stessa protezione); un cookie HttpOnly richiederebbe di ripensare tutta l’autenticazione: rinviato. Il token è già tolto dall’indirizzo subito dopo l’arrivo |
| FATTO 1.8.6 | frontend Utenti.js | testo d'aiuto CSV (ora si manda un link, non la password); endpoint di esportazione utenti — testo d’aiuto aggiornato; l’endpoint `/auth/users/export` esiste già (verificato) |
| FATTO 1.8.6 | frontend Corsi.js, EdizioneDetail.js, StatoPiattaforma.js | gestione errori, array di validazione mostrato grezzo, tentativo di nuovo caricamento |
| FATTO 1.8.5 | api/sso.py | gestire errori inattesi nella callback |
| FATTO 1.8.5 | api/edizioni.py | non mandare inviti calendario per sessioni in bozza |
| CHIUSO | api/auth.py | inviti CSV dopo il commit: corretto nella 1.8.3 |

## PR #3 — fasi 1.2.0, 1.2.1 e 1.3.0 (12 commenti in linea, tutti minori, + 3 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| CHIUSO | api/password_reset.py | email di reset durante la richiesta: già in sottofondo dalla 1.8.3 |
| FATTO 1.8.4 | api/password_reset.py | `genera` non rifiuta richieste di account disattivati o non locali (verificato nel codice: manca il controllo) |
| FATTO 1.8.4 | api/privacy.py | il PDF dell'informativa è servito da `/uploads/...` senza autenticazione: servirlo da un endpoint con login (verificato) |
| FATTO 1.8.5 | api/matrice_ispezione.py | il conteggio documenti (limite pacchetto) avviene prima di verificare che i file esistano (verificato); righe storiche del pacchetto senza perimetro; ZIP costruito in modo sincrono senza limite su PDF/Excel; N+1 sulle righe del registro; verificare il BOM nell'`indice_documenti.csv` — fatti: conteggio dopo il controllo dei file, ricerche accorpate, BOM verificato presente; rinviati: righe storiche e ZIP sincrono (gira già fuori dal ciclo principale, con file temporaneo su disco e limite di documenti) |
| FATTO 1.8.6 | frontend ImpostazioniUtente.js | errori non gestiti (informativa, esportazione dati, URL calendario); schede non usabili da tastiera |
| FATTO 1.8.6 | frontend InformativaPrivacy.js | errore di caricamento iniziale non gestito |
| FATTO 1.8.6 | frontend MatriceFormativa.js | richiesta fallita e risposte vecchie che sovrascrivono le nuove |
| FATTO 1.8.6 | frontend Piattaforma.js | errori in `rimuoviIcona` |

## PR #4 — fasi 1.4.0, 1.4.1 e 1.4.2 (9 commenti in linea)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | api/entra_sync.py | `applica` ricalcola il piano da Entra invece di applicare quello visto in anteprima (verificato): legare l'applicazione all'anteprima (impronta del piano) |
| FATTO 1.8.4 | services/offboarding.py | `posti_liberati` conta anche chi era in lista d'attesa (verificato); promozione dalla lista d'attesa legata al flag della sessione: rivedere il caso con lista disabilitata |
| FATTO 1.8.5 | tests/conftest.py | l'URL del database si scompone con `rpartition("/")`: usare il parser di SQLAlchemy (regge password e parametri con "/") |
| FATTO 1.8.5 | tests/test_privacy.py | l'asserzione sull'esportazione dati non controlla `token_version` — l’asserzione ora è stretta e ha rivelato che l’esportazione includeva `token_version` (dato interno di sicurezza): tolto |
| FATTO 1.8.6 | frontend Ordinabile.js | l'ordinamento per colonna non è azionabile da tastiera |
| FATTO 1.8.6 | frontend Fabbisogno.js | chiave stabile per le righe rimovibili del modulo; errori non gestiti in `delega` |
| FATTO 1.8.6 | frontend FabbisognoAdmin.js | errori nella creazione campagna non mostrati; "Azzera" non coerente con il contesto della campagna |

## PR #5 — fasi 1.5.0, 1.5.1 e 1.6.0 (6 commenti in linea + 1 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.5 | services/rinnovo.py | `ripeti_entro` (test non superato) può fissare una scadenza più vicina di quella del corso e ora viene ignorata (verificato: il campo esiste e le notifiche lo usano, il rinnovo no) |
| FATTO 1.8.5 | services/rinnovo.py | un'iscrizione aperta a una sessione non più utilizzabile (già iniziata, ferma) blocca il rinnovo della persona (verificato: il controllo `gia_iscritto` conta anche sessioni passate e bozze) |
| CHIUSO | services/configurazione.py | un gruppo senza `percorso` nel file importato manda in errore l'ordinamento: segnalarlo o saltarlo con avviso (verificato; già rifiutato con errore 400 che nomina il campo, c'è il test) |
| FATTO 1.8.6 | frontend AlberoOrigine.js | l'albero mostrato non è legato all'`id`: si aggiorna male cambiando richiesta |
| FATTO 1.8.6 | frontend Configurazione.js | `r.sezioni[k]` senza controllo se manca la chiave |

## PR #6 — fasi 1.7.0, 1.7.1 e 1.7.2 (4 commenti in linea + 1 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.5 | api/etichette.py, services/etichette.py | identificativi delle etichette non UUID nei filtri (`etichette=...`) arrivano al DB e danno errore 500: validarli prima (verificato: nessun controllo) |
| FATTO 1.8.5 | services/etichette.py | la migrazione delle categorie in etichette Tematica può creare duplicati (nome troncato a 80 caratteri ma cercato per esteso) e violare `uq_etichetta_famiglia_nome` (verificato nel codice) |
| FATTO 1.8.6 | frontend Etichette.js | `chiama` nasconde gli errori: i moduli di rinomina e unione si chiudono anche se la richiesta fallisce |
| FATTO 1.8.4 | api/password_reset.py + test | il riscatto del token di reset non è protetto da una corsa: due richieste in parallelo possono usarlo entrambe (verificato: nessun blocco della riga); aggiungere blocco e un test di copertura |

## PR #7 — fasi 1.8.0, 1.8.1, 1.8.2 e storico (5 commenti in linea + 5 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.5 | app/schema_legacy.py | `porta_a_baseline` usa `Base.metadata.create_all` con i modelli di OGGI: per un database precedente alle migrazioni, quando arriveranno migrazioni 0002+ lo schema "0001" non sarebbe più quello di partenza (verificato nel codice). Congelare lo schema 0001 (rilievo più importante di questa PR) — non congelato (nessun database vecchio da portare avanti): regola scritta in schema_legacy.py, ogni migrazione dalla 0002 è idempotente |
| FATTO 1.8.5 | app/migrazioni.py | dopo un errore la transazione è interrotta e lo sblocco `pg_advisory_unlock` fallisce: fare rollback prima di rilasciare il blocco (verificato) |
| FATTO 1.8.5 | services/inviti.py | normalizzare `SSO_PUBLIC_URL` (spazi, barre finali) prima di usarlo come alternativa (verificato: solo `rstrip("/")`) |
| FATTO 1.8.7 | README.md | indicare l'URL HTTPS pubblico e limitare l'accesso diretto alla porta 2018 (documentazione; la parte di rete è infrastruttura dell'utente: solo testo) — aggiunto l’indirizzo HTTPS pubblico e l’indicazione di non esporre la porta 2018 direttamente (solo testo) |
| FATTO 1.8.7 | ROADMAP.md (riga 10) | cita ancora i "Formatori" tra i ruoli di sistema (verificato): i ruoli fissi sono Admin tecnico, Ufficio Formazione e Utenti |
| FATTO 1.8.7 | docs/guida-amministratore.md, guida-utente.md | allineare le regole della password nelle due guide (la politica è: 14 caratteri, maiuscola, numero, carattere speciale) — la guida utente era già corretta, allineata la guida amministratore |
| FATTO 1.8.5 | scripts/modo-revisione.sh | togliere il file indice temporaneo anche in caso di errore |
| FATTO 1.8.5 | tests/test_revisione2.py, test_revisione3.py | asserzioni mancanti: successo dell'annullamento da lista d'attesa e dell'aggiornamento del test; validare la risposta di riserva come PNG |

## PR #8 — fase 1.8.3 (6 commenti in linea: sono sulle mie correzioni della quarta revisione)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | api/auth.py (import CSV) | `email_inviata` risulta vera anche se l'invio è solo programmato: se poi l'email fallisce, l'admin non vede mai la password temporanea (verificato: `inviata = bool(link)`). Segnalare "invito programmato" e dare un modo di recupero |
| FATTO 1.8.4 | api/test.py | il formatore di una sessione in **bozza** ha ancora accesso al test e alle risposte corrette: escludere anche le bozze (verificato: il filtro toglie solo chiuse e annullate) |
| FATTO 1.8.4 | services/configurazione.py | `is_ufficio` nullo nel file importato diventa `False` e cancella l'ufficio esistente (verificato: `bool(d["ufficio"])`); trattarlo come campo assente |
| FATTO 1.8.4 | services/entra_sync.py | con meno di 4 utenti in ambito il minimo di 2 lascia passare tutte le disattivazioni (verificato: 2 su 2, 2 su 3): il freno deve valere per ogni dimensione |
| FATTO 1.8.4 | services/export.py | l'apice di neutralizzazione compare anche nelle celle dei PDF: applicarla solo a CSV ed Excel |
| CHIUSO | services/export.py | testi che iniziano con un ritorno a capo o spazi prima del `=`: probabilmente innocui (in un campo tra virgolette restano testo), da provare in Excel/LibreOffice prima di cambiare — con uno spazio o un a capo davanti al segno il campo resta testo; non provato in Excel, rischio basso: lasciato com’è |

## Le prossime PR
Aggiungere qui sotto una sezione per ogni PR, appena arriva la review della fase.

## PR #9 (1.8.4, sicurezza e integrità dati)

| Stato | File | Rilievo |
|---|---|---|
| CHIUSO | main.py (UploadsPubblici) | `..` nel percorso aggirerebbe l'elenco dei file pubblici (verificato con file veri e `curl --path-as-is`: 404, perché Starlette normalizza il percorso prima; aggiunta comunque la normalizzazione esplicita e il test) |
| FATTO 1.8.5 | services/entra_sync.py | l'impronta del piano non includeva i valori scritti (nome, data di ingresso): ora li include (test) |
| FATTO 1.8.5 | migrations 0002 | i doppioni degli inviti tenevano il più vecchio anche se più indietro: ora si tiene prima `risposto`, poi `delegato` |
| FATTO 1.8.5 | frontend ImpostazioniUtente.js | `apriFile` non importato: il pulsante dell'informativa PDF dava errore (bug vero della 1.8.4) |
| FATTO 1.8.5 | gradimenti.py, iscrizioni.py, migrations 0002 | `raise ... from err`; `postgresql_where` tolto da `drop_index` |
| FATTO 1.8.5 | docs/rilievi-coderabbit.md | testo sul calendario delle correzioni e tabella con quattro celle: sistemati |
| CHIUSO | api/fabbisogno.py | bloccare anche la riga della campagna contro la chiusura in parallelo: rischio minimo (chiusura e risposta nello stesso istante), rinviato |
| CHIUSO | test password_reset | test di riscatto concorrente: richiede due connessioni sincronizzate, il blocco di riga è provato dal codice; non aggiunto |

## PR #10 (1.8.5, correttezza e prestazioni)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.5 | api/push.py | la sottoscrizione dopo due tentativi falliti rispondeva "ok": ora risponde 409 |
| FATTO 1.8.5 | services/certificati.py | coordinate non convertibili (intero di 400 cifre): rifiutate al salvataggio (limite -10000..100000) e gestite anche in generazione |
| FATTO 1.8.5 | docs/rilievi-coderabbit.md | note con una quarta cella nelle righe 27, 32, 64, 106: sistemate |

## PR #11 (1.8.6, interfaccia)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.6 | frontend DashboardKpi.js, FabbisognoAdmin.js, ImpostazioniUtente.js | ruoli `tab` senza pannelli e frecce: tolti, le schede sono pulsanti con `aria-pressed` |
| FATTO 1.8.6 | frontend EdizioneDetail.js | «Riprova» non azzerava l'errore: ora `load` lo azzera all'inizio |
| FATTO 1.8.6 | frontend Fabbisogno.js | errore generale mai azzerato dopo un ricaricamento riuscito: azzerato all'inizio di `load` |
| FATTO 1.8.6 | frontend FabbisognoAdmin.js | errore di pagina persistente tra le schede: azzerato a ogni caricamento e al cambio scheda |
| FATTO 1.8.6 | frontend Azienda.js | «Riprova» mancante se il caricamento fallisce: aggiunto |

## PR #12 (1.8.7, documenti e rifiniture)

| Stato | File | Rilievo |
|---|---|---|

## PR #13 (1.9.0, video protetti e CORS)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.0 | api/video.py | due caricamenti dello stesso file usavano lo stesso nome provvisorio e si mescolavano: nome unico per ogni caricamento |
| FATTO 1.9.0 | api/video.py | indirizzo valido di un video cancellato dava errore 500: ora 404 (aggiunto test) |
| FATTO 1.9.0 | VideoPlayer.js | risposte di un video precedente potevano sostituire quello corrente: scartate le richieste superate e azzerato l'accesso al cambio video |
| FATTO 1.9.0 | VideoPlayer.js | il contatore dei tentativi non si azzerava dopo una riproduzione riuscita o con «Riprova»: ora sì |

## PR #14 (1.9.1, registro attività)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.1 | services/audit_manutenzione.py | file provvisorio con nome fisso: con più processi due esportazioni si mescolavano. Nome unico per ogni esportazione |
| FATTO 1.9.1 | services/audit_manutenzione.py | se un collettore sposta o cancella i file, i giorni venivano riesportati e la pulizia si bloccava: i giorni esportati sono ora registrati nel database (tabella `audit_esportazioni`, migrazione 0004), indipendentemente dai file |
| FATTO 1.9.1 | services/audit_manutenzione.py | cancellazioni con commit intermedi e traccia a parte: ora cancellazioni e riga «AUDIT_PULIZIA» stanno in una sola transazione |
| FATTO 1.9.1 | tests/test_registro_attivita.py | test dipendente dall'ora di esecuzione (tra 00:00 e 01:00 UTC): eventi ora a mezzogiorno UTC di giorni fissi |

## PR #15 (1.9.2, pagina Informazioni)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.2 | ROADMAP.md | la voce 1.9.2 non citava l'azienda tra le informazioni visibili agli utenti: aggiunta |
| CHIUSO | ROADMAP.md | avviso di LanguageTool sugli asterischi: falso allarme, è il grassetto Markdown usato in tutto il file |

## PR #16 (1.9.3, cifratura)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.3 | services/cifratura_ops.py | lo strumento includeva `/app/videos` tra le cartelle da cifrare, ma la riproduzione non decifra ancora: i video sarebbero diventati illeggibili. Tolta la cartella dei video fino alla 1.9.4 (aggiunto test) |
| FATTO 1.9.3 | services/cifratura_ops.py | la conversione leggeva ogni file per intero in memoria (due copie): ora lettura e scrittura a blocchi (`leggi_a_blocchi`) |
| FATTO 1.9.3 | api/calendario.py | risposta con il token in chiaro senza `Cache-Control: no-store`: aggiunto (con test) |
| FATTO 1.9.3 | migrations/0005 | `downgrade` nominava un vincolo che poteva non esistere e non ricreava quello su `calendar_token`: ora ricrea il vincolo e toglie la colonna dell'impronta con il suo vincolo |
| CHIUSO | api/matrice_ispezione.py | ZIP: file decifrati uno alla volta, picco di memoria = un file (max 25 MB); da rivedere se i limiti o i video entrano in quel percorso |
| FATTO 1.9.3 | tests/test_cifratura.py | test casuale: con un file di 1 byte quel byte poteva comparire per caso nel file cifrato; il controllo ora vale solo per contenuti di almeno 32 byte |

## PR #17 (1.9.4, video in più qualità e cifrati)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.4 | nginx/nginx.conf | la regola nuova per i video intercettava anche il caricamento dei sottotitoli e abbassava il limite a 1 MB: riprodotto (2,5 MB respinti con 413), aggiunto `client_max_body_size 3M`; verificato dopo la correzione (2,5 MB arrivano al backend, 3,5 MB respinti) |
| FATTO 1.9.4 | api/video.py | elenco e dettaglio video: una query per ogni video per leggere le qualità (la pagina Video si aggiorna ogni 4 secondi): caricamento delle qualità in blocco, con test che conta le query |
| FATTO 1.9.4 | VideoPlayer.js | la qualità automatica veniva ricalcolata a ogni disegno con i valori di rete del browser: poteva cambiare a metà visione e far ricominciare il video. Ora si decide una volta quando le qualità sono note e resta ferma (anche se gli indirizzi si rinnovano) |

## PR #18 (1.9.5, dipendenze, immagini e controlli di sicurezza)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.5 | scripts/controlli-sicurezza.sh, docker-compose.yml | lo script scansionava `elearning-backend`/`elearning-frontend` dando per scontato che fossero i nomi delle immagini, ma Compose li ricava dal nome della cartella del progetto: con un'altra cartella avrebbe scansionato un'immagine vecchia o nessuna. Nomi esplicitamente fissati (`image:`) nel compose per backend e frontend |

## PR #20 (1.9.7, dati personali cifrati nel database)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.7 | api/about.py, docs/sicurezza.md | il conteggio dei valori in chiaro nella pagina Stato guarda solo le ultime 10000 righe del registro: il limite è ora dichiarato nel changelog e nel documento di sicurezza |
| FATTO 1.9.7 | docs/sicurezza.md | il testo diceva che chi ha il database non può confrontare le impronte: errato, due valori uguali hanno la stessa impronta (confrontabili tra loro; non si può calcolare l'impronta di un candidato senza la chiave). Testo corretto |
| CHIUSO | api/admin_tecnico.py | nota senza modifiche richieste dalla review stessa (filtri email/IP: contratto verificato dai test) |

Seconda review (sul commit di correzione):

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.9.7 | api/auth.py (creazione utente) | due richieste insieme con la stessa email scritta con maiuscole diverse davano errore 500 al posto di «Email già esistente»: ora l'inserimento è in un punto di salvataggio e il conflitto diventa il 400 previsto |
| FATTO 1.9.7 | api/auth.py (importazione CSV) | lo stesso conflitto fermava l'intera importazione: ora è un errore di riga e le altre righe proseguono |
| FATTO 1.9.7 | api/sso.py | creazione al primo accesso SSO: in caso di conflitto si riprende l'utente creato dall'altra richiesta, con gli stessi controlli di collegamento |
| FATTO 1.9.7 | services/entra_sync.py | sincronizzazione Entra: in caso di conflitto l'utente è saltato (non contato né registrato) e la sincronizzazione prosegue |

Provati con test (creazione utente e CSV, corsa simulata). SSO ed Entra: modifica fatta e suite intera verde, ma senza un test dedicato alla corsa.

## PR #21 (2.0.0, pronta per l'uso aziendale)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.0.0 | api/about.py | il changelog diceva «controlli automatici a ogni modifica»: il flusso GitHub gira su pull request e push su master, e lo script locale non lancia i test. Frase riscritta con le condizioni esatte |

## PR #22 (2.1.0, pagina Utenti a schede)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.1.0 | pages/Utenti.jsx | il numero di pagina non era annunciato dai lettori di schermo quando cambia: aggiunto `aria-live="polite"` all'indicatore di pagina e, per lo stesso motivo, al conteggio dei risultati |

## PR #23 (2.2.0 - 2.3.1: permessi, uffici, mansioni, nome e cognome)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.3.2 | api/auth.py | importazione CSV: la variabile del ciclo sulle mansioni sovrascriveva `nome`, e l'invito email partiva a «Preposto Rossi» invece di «Mario Rossi». Variabile rinominata e invito con il nome intero salvato; test con l'invio attivo |
| FATTO 2.3.2 | api/groups.py | eliminare un ufficio usato da un percorso (assegnazione automatica) o dal fabbisogno dava errore del database (500): ora risposta 400 con il motivo |
| FATTO 2.3.2 | services/entra_sync.py | con il solo nome visualizzato la sincronizzazione confrontava la divisione del nome con nome e cognome salvati, e a ogni giro annullava una correzione fatta a mano: ora confronta con il nome intero salvato e divide solo se è cambiato |
| FATTO 2.3.2 | frontend/src/api.js | la richiesta del profilo all'avvio non aveva un limite di tempo: con il server che non risponde la pagina restava bianca. Limite di 5 secondi |
| FATTO 2.3.2 | pages/Percorsi.jsx | modificando un percorso assegnato a una mansione non più attiva la tendina non la offriva e il modulo non si poteva salvare: la mansione scelta resta tra le opzioni («non attiva») |
| FATTO 2.3.2 | services/configurazione.py (nota) | importando un file vecchio il cui gruppo non-ufficio ha lo stesso nome di un ufficio esistente, il percorso usa l'ufficio senza dirlo: aggiunto un avviso |
| FATTO 2.3.2 | docs/guida-amministratore.md (nota) | la guida non citava l'assegnazione dei percorsi a ufficio e mansione: aggiornata |
| FATTO 2.3.2 | docs/progetto-ruoli-mansioni.md (nota) | la frase «nessun codice scritto» era superata: il documento ora dice che la release è stata realizzata |

## PR #24 (2.3.3, importazione da Excel con controllo prima)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.3.3 | services/import_utenti.py | un CSV malformato (virgolette mai chiuse) dava errore 500: ora 400 con una spiegazione |
| FATTO 2.3.3 | services/import_utenti.py | due uffici con lo stesso percorso intero si sovrascrivevano in un dizionario e l'importazione ne sceglieva uno a caso senza avviso: ora sono ambigui, la persona è creata senza ufficio e il riepilogo lo dice |
| FATTO 2.3.3 | pages/Utenti.jsx | il pulsante del riepilogo non compariva se le righe erano solo «ignorate» (per esempio cessati non trovati): ora compare |
| FATTO 2.3.3 | pages/Utenti.jsx | durante l'importazione la finestra si poteva chiudere (Annulla, Esc, clic fuori) dando l'impressione di aver annullato: ora è bloccata finché la richiesta non finisce |
| FATTO 2.3.3 | api/auth.py, services/import_utenti.py | la conferma rielaborava il file senza agganciarsi a quanto visto nel controllo (rilievo maggiore): il controllo restituisce un'impronta del risultato (riga, email, esito, avvisi), la conferma la rimanda e, se il risultato è cambiato, l'importazione si ferma con 409 senza fare nulla |

| CHIUSO 2.3.4 | (riepilogo, controllo «Docstring Coverage») | avviso non legato al codice: copertura delle docstring al 22% contro una soglia dell'80% (comparso anche sulle PR #20 e #22). Valutato e non adottato: per raggiungerla servirebbe una descrizione formale per ogni funzione, anche di una riga, senza migliorare sicurezza o correttezza; nel progetto si commenta dove serve spiegare il perché. Aggiunto `.coderabbit.yaml` che spegne il controllo (chiave `reviews.pre_merge_checks.docstrings.mode: off`): verificato sulla review della PR #25, dove l'avviso non compare più |

## PR #25 (2.3.4, ruoli a capsule e «Docente»)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.3.4 | api/about.py | nella voce storica 2.2.0 la colonna del CSV era stata rinominata «docente» dalla sostituzione globale: ripristinata «formatore» (nome di allora) con l'indicazione che dalla 2.3.4 si chiama docente |
| FATTO 2.3.4 | docs/guida-amministratore.md | la guida diceva «filtra per permessi, tipo»: ora «ruoli» (il filtro Tipo non c'è più) |
| FATTO 2.3.4 | docs/progetto-ruoli-mansioni.md | la sostituzione globale aveva trasformato `is_formatore` (nome vero nel codice) in `is_docente` in due righe: ripristinato, con la nota che in app si chiama «Docente» |
| FATTO 2.3.4 | pages/Utenti.jsx | il modulo di modifica di un utente esterno non mostrava le capsule dei ruoli: ora mostra «Docente» ed «Esterno» |

## PR #26 (2.4.0, etichette libere, corsi a schede, player compatto)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.4.0 | services/etichette.py | la conversione del vecchio campo Categoria in etichette si saltava se esisteva già una qualunque famiglia: ora i corsi con una categoria si convertono comunque, nella famiglia «Tematica» (creata o riusata senza toccare le altre, e senza duplicare i collegamenti); fatta la conversione il vecchio campo si svuota, così non si ripete e chi toglie l'etichetta non se la ritrova |
| FATTO 2.4.0 | api/video.py | un docente assegnato alla sessione (senza il permesso Formazione) vedeva nella pagina il pulsante di anteprima del video ma il server rispondeva «non trovato»: ora i docenti della sessione possono vedere il video e ottenerne l'accesso; un docente di un'altra sessione o un utente qualunque no (errore mio della 2.4.0) |
| FATTO 2.4.0 | tests/test_iscrizioni.py (nota) | il test sulle iscrizioni annullate passava anche se l'elenco restituiva solo quelle «iscritto»: ora controlla che lista d'attesa e corsi completati restino visibili |

## PR #27 (2.4.1, sezione Video a schede)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.4.1 | api/video.py, pages/Video.jsx | l'eliminazione si bloccava solo con il video «in elaborazione»: eliminando appena caricato (il lavoro sta per partire) o a video pronto mentre si preparano le qualità più alte si lasciavano file orfani o si faceva fallire il lavoro. Ora è bloccata anche con «caricato» e con le altre qualità in preparazione (server e pulsante, con la spiegazione); se un riavvio interrompe il lavoro, all'avvio il video viene già sistemato e torna eliminabile |

## PR #28 (2.5.0, durata e sessioni)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.5.0 | api/edizioni.py | duplicando una sessione chiusa la copia si portava dietro la durata congelata alla chiusura (che poteva essere solo quella ereditata dal corso, ormai superata). Ora la copia di una sessione chiusa riparte dal corso; si mantiene la durata forzata di una sessione non chiusa. Limite noto: la durata forzata di una sessione chiusa non si distingue da quella congelata e non viene copiata |
| FATTO 2.5.0 | services/durata.py | una sessione chiusa senza alcuna durata riprendeva dal corso quella inserita in seguito, cambiando lo storico. Ora una sessione chiusa senza durata propria resta senza |

## PR #29 (2.6.0, Il mio team e corsi aperti)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.6.0 | api/edizioni.py, services/configurazione.py | l'iscrizione diretta del responsabile escludeva solo due valori: un modo sconosciuto (refuso in una configurazione importata) apriva il corso. Ora si ammette solo «diretta»; l'importazione scarta i valori non ammessi (il corso resta chiuso o come era) |
| FATTO 2.6.0 | api/richieste_iscrizione.py | la richiesta si legge ora con blocco di riga: due approvazioni/rifiuti contemporanei non lasciano una richiesta «rifiutata» con la persona iscritta |
| FATTO 2.6.0 | api/richieste_iscrizione.py | l'approvazione per una persona disattivata la iscriveva: ora risponde 400 e invita a rifiutare |
| FATTO 2.6.0 | api/team.py, api/richieste_iscrizione.py, services/iscrizioni.py | sessioni pianificate già finite accettavano richieste e approvazioni: nuovo controllo condiviso `sessione_finita` (usato anche nell'elenco dei corsi disponibili) |
| FATTO 2.6.0 | pages/IlMioTeam.jsx | la vista «Per persona» raggruppava per nome: due omonimi si fondevano; ora per identificativo |

## PR #30 (2.7.0, Catalogo e corsi sempre disponibili)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.7.0 | services/completamento.py | due richieste contemporanee sulla stessa iscrizione (due heartbeat del player, due schede, un heartbeat e un tentativo del test) potevano emettere due attestati: la riga dell'iscrizione si rilegge ora con blocco prima di controllare lo stato, così la seconda trova già «completato» |

## PR #31 (2.7.1, eliminare corsi e sessioni, sessioni da pubblicare)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.7.1 | services/elimina_corso.py | eliminando un corso, una sessione chiusa con sole iscrizioni annullate veniva cancellata, mentre la singola sessione chiusa non si può eliminare: ora una sessione chiusa blocca anche l'eliminazione del corso |
| FATTO 2.7.1 | pages/Edizioni.jsx | creazione e pubblicazione condividevano lo stesso controllo degli errori: se la pubblicazione falliva dopo la creazione, il modulo restava pieno e un nuovo invio creava una seconda sessione. Ora i due passaggi sono separati: se la pubblicazione fallisce si avvisa e si apre la sessione creata |

## PR #32 (2.7.2 e 2.7.3, vista discente e storico)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.7.4 | components/VideoPlayer.jsx | cambiando sessione il player riutilizzato poteva tenere l'avanzamento dell'iscrizione precedente e accettare risposte vecchie: ora si azzera a ogni iscrizione e le risposte di un'altra iscrizione si scartano |
| FATTO 2.7.4 | components/VideoPlayer.jsx, avanzamentoVideo.js | un salto accettato (entro 2 secondi) faceva avanzare il traguardo: con tanti piccoli salti si attraversava il video. Ora i salti non contano come visione e sono ammessi solo fino al punto già guardato |
| FATTO 2.7.4 | pages/SessioneDiscente.jsx | se la richiesta dell'iscrizione falliva la pagina restava su «Caricamento...» senza errore: ora mostra l'errore con «Riprova» |
| FATTO 2.7.4 | pages/StoricoCorsi.jsx | un errore in una delle due richieste lasciava «Caricamento...» o «nessun attestato»: i due caricamenti hanno ora ciascuno il proprio stato di errore |
| FATTO 2.7.4 | pages/StoricoCorsi.jsx | di un'iscrizione con più attestati se ne vedeva uno: ora una riga per attestato |
| FATTO 2.7.4 | requirements.txt | non è un rilievo di CodeRabbit ma il controllo `pip-audit` della CI è fallito: 8 vulnerabilità note di Pillow 12.3.0, corrette passando alla 13.0.0 (`Image.LANCZOS` → `Image.Resampling.LANCZOS`) |

### PR #32, seconda lettura (commit della 2.7.4)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.7.4 | components/VideoPlayer.jsx | l'iscrizione corrente si scriveva in un riferimento durante la costruzione della pagina (React può scartare quella costruzione): ora si aggiorna in un effetto prima di quello dell'avanzamento |
| FATTO 2.7.4 | pages/Catalogo.jsx | cercando una parola che esiste solo tra i corsi già completati comparivano due messaggi «nessun risultato» prima dei risultati: ora si nascondono se tra i completati c'è una corrispondenza |
| FATTO 2.7.4 | pages/StoricoCorsi.jsx | dopo «Riprova» una vecchia richiesta in ritardo poteva sovrascrivere il risultato nuovo con un errore: ogni caricamento ha ora una sua generazione e le risposte vecchie si ignorano |
| FATTO 2.7.4 | api.js | «Visualizza» apriva la scheda solo dopo aver scaricato il PDF e il browser poteva bloccarla senza avvisare: la scheda si apre subito nel gesto dell'utente, poi si carica il file, e si chiude se il file non arriva (vale anche per l'informativa privacy e le impostazioni) |
| NON NECESSARIO | components/VideoPlayer.jsx | segnalazione già vista (salti brevi che avanzano il traguardo): CodeRabbit stesso nota che `saltoConsentito` rifiuta già i salti oltre il punto raggiunto; verificato con lo script di prova |

## PR #33 (2.8.0, questionari di gradimento)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.8.0 | api/questionari.py | due salvataggi in parallelo con lo stesso nome passavano entrambi il controllo e uno dava errore 500 al salvataggio: ora il vincolo del database è gestito (anche alla modifica) e la risposta è lo stesso 400 «Esiste già un questionario con questo nome» |
| FATTO 2.8.0 | api/gradimenti.py | nel riepilogo dei gradimenti le risposte aggiuntive si leggevano una query per volta: ora si caricano insieme alle altre |

### PR #33, seconda lettura (commento fuori dal diff)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.8.0 | api/gradimenti.py | un doppio invio in parallelo del gradimento poteva dare errore 500: l'errore del database usciva prima del blocco che lo gestisce. Ora inserimenti e salvataggio sono dentro lo stesso blocco e la risposta è il solito 400 |
| FATTO 2.8.0 in modo diverso dal suggerito | api/questionari.py | due domande con lo stesso testo fondevano le risposte nei report e nel CSV. Il suggerimento (usare l'identificativo della domanda) avrebbe spezzato i report a ogni modifica del questionario, perché a ogni salvataggio le domande si ricreano con nuovi identificativi; si è scelto di non ammettere due domande con lo stesso testo nello stesso questionario |

## PR #34 (2.9.0, come si accede e quando è disponibile)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.9.0 | services/iscrizioni.py | `sessione_finita` valeva solo per le sessioni «pubblicate»: una sessione «in corso» oltre la data di fine accettava ancora richieste e iscrizioni. Ora vale per entrambe le fasi aperte (senza chiudere la sessione) |
| FATTO 2.9.0 | api/evidenze.py | la chiusura di una sessione e il completamento automatico di un video potevano incrociarsi sulla stessa iscrizione (doppio attestato): la chiusura rilegge e blocca ogni iscrizione prima di trattarla, e il completamento automatico fa lo stesso. Nessun test riproduce la corsa; resta il test sull'assenza di doppi attestati alla chiusura |
| FATTO 2.9.0 | api/video.py | gli indirizzi firmati durano due ore e, finita la sessione, continuavano a servire video e sottotitoli: ora si ricontrolla a ogni richiesta (sessione finita o chiusa, iscrizione annullata); chi gestisce non è toccato. Un video inesistente risponde sempre 404 |
| FATTO 2.9.0 | services/completamento.py | l'audit del completamento automatico diceva «sessione sempre aperta» anche per i video con data: ora «video seguito fino alla fine» |
| FATTO 2.9.0 | services/configurazione.py | l'importazione valutava le due approvazioni solo sui valori del file, non sul corso già presente: poteva lasciarle entrambe attive. Ora se il file ne imposta una sola vince quella (l'altra si spegne); se le imposta entrambe resta quella del responsabile |
| FATTO 2.9.0 | services/iscrizioni.py | per un video il blocco non copriva le sessioni chiuse prima della fine o senza data di fine, né quelle annullate o ancora in bozza: ora non sono disponibili a chi segue (chi gestisce vede sempre) |
| FATTO 2.9.0 | pages/SessioneDiscente.jsx | una pagina aperta prima dell'inizio del video restava senza video dopo l'ora di inizio: ora si ricarica da sola all'ora (timer ripulito allo smontaggio) |

## PR #35 (2.10.0, percorsi che iscrivono)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.10.0 | api/edizioni.py | pubblicando una sessione chi era già iscritto riceveva l'invito al calendario due volte (una dal giro di pubblicazione, una dall'avanzamento dei percorsi): ora prima il giro degli iscritti, poi i percorsi, ognuno una volta sola |
| FATTO 2.10.0 | services/configurazione.py | importando un file fatto prima della 2.10.0 la modalità dei percorsi già presenti veniva dedotta e sovrascritta: un percorso sequenziale (che non ha prerequisiti scritti) tornava «libero», togliendo i blocchi a tutti gli assegnati. Ora la modalità si deduce solo per i percorsi nuovi; per quelli esistenti cambia solo se il file la dichiara |
| FATTO 2.10.0 | services/percorsi_iscrizioni.py, api/percorsi.py | le persone esterne (docenti di terzi) non possono essere iscritte ma risultavano «in attesa di una sessione» per sempre, con un avviso settimanale alla Formazione: ora si saltano nell'avanzamento e non si assegna loro il percorso (messaggio nell'esito) |
| FATTO 2.10.0 | components/PersonePercorso.jsx | la conferma di «Togli il percorso» diceva che le iscrizioni restano e insieme che si annullano: ora dice che restano e vanno annullate una per una dalle sessioni se non servono |
| FATTO 2.10.0 | pages/Percorsi.jsx, api/percorsi.py | le propedeuticità spuntate restavano legate al numero d'ordine: cambiando i numeri o togliendo un corso potevano puntare al corso sbagliato o sparire. Ora il modulo le tiene legate al corso e le trasforma in numeri solo all'invio; il server rifiuta una propedeuticità che non si riferisce a un corso del percorso (prima la scartava in silenzio) |
| FATTO 2.10.0 | api/catalogo.py | (suggerimento) il blocco di un corso si ricalcolava per ogni sessione: ora una volta per corso |

## PR #36 (2.11.0, 2.12.0 e 2.12.1)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.12.1 | services/copertine.py | non è di CodeRabbit ma del controllo di sicurezza della CI (Bandit, B324, gravità alta): il codice di versione della copertina usava `sha1`. Non era un uso di sicurezza (serve solo a cambiare l'indirizzo quando cambia l'immagine), ma si usa `sha256` invece di zittire l'avviso. Prima di pubblicare avevo lanciato la suite ma non Bandit: da ora Bandit, pip-audit e npm audit si lanciano in locale prima di ogni push, insieme alla suite |
| FATTO 2.12.1 | services/copertine.py, api/corsi.py | sostituendo una copertina il file nuovo finiva sopra il vecchio prima del salvataggio nel database: se questo falliva, il database teneva il codice di versione vecchio ma il file era già quello nuovo. Ora ogni copertina ha un nome proprio, il file vecchio si toglie solo dopo il salvataggio e quello nuovo si toglie se il salvataggio fallisce (test con salvataggio guasto) |
| FATTO 2.12.1 | components/CampoCopertina.jsx | il campo del file era nascosto con `display: none`, quindi chi usa la tastiera non poteva caricare la copertina: ora il campo è nascosto con `hidden` e c'è un vero pulsante, raggiungibile con Tab |
| FATTO 2.12.1 | components/Shell.jsx | l'avviso «sei passato a…» restava acceso se si cambiava pagina prima dei 2,8 secondi, e la scelta dal selettore degli spazi poteva restare segnata per un collegamento successivo: ora il flag si legge e si azzera subito e l'avviso si spegne all'uscita |
| FATTO 2.12.1 | pages/DashboardKpi.jsx | «edizioni» al posto di «sessioni» in titoli, colonne e messaggi della pagina dei KPI: uniformato al nome usato nel resto della piattaforma |
| FATTO 2.12.1 | spazi.js | l'ultimo spazio e le ultime pagine ricordate valevano per il browser, non per la persona: chi entrava dopo sullo stesso computer ritrovava le pagine di chi c'era prima. Ora le chiavi includono l'id della persona |
| FATTO 2.12.1 (in parte) | api/spazi.py, components/Shell.jsx | (suggerimento) i numeri del menu contavano gli iscritti di ogni sessione da chiudere senza usarli: ora c'è un conteggio che non li calcola. **Non adottato**: la cache di 60 secondi e il togliere l'aggiornamento a ogni cambio pagina, perché i numeri devono scendere subito dopo aver risolto una richiesta e con il conteggio leggero la richiesta costa poco |
| FATTO 2.12.1 | api/corsi.py | (fuori dal diff) togliendo la copertina il file veniva cancellato prima del salvataggio nel database: se questo falliva, il corso restava con una copertina che non esiste più. Ora il file si cancella solo dopo il salvataggio, come per il caricamento (test con salvataggio guasto) |

## PR #37 (2.12.2, pulizia del codice)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.12.2 | tests/test_concorrenza.py | il test leggeva `i.id` dopo il commit, quando l'oggetto è scaduto e la sessione è condivisa con i due fili: l'id si legge ora prima. |
| FATTO 2.12.2 | docs/roadmap-archivio.md | due voci ancora aperte (periodo di conservazione dei dati con il DPO, assegnazione automatica di ruoli dall'accesso aziendale) erano finite nell'archivio insieme alle parti spedite: riportate nella roadmap sotto «Da definire». Ricontrollato tutto l'archivio: le altre voci con «da valutare» sono già nella roadmap o sono chiuse. |
| FATTO 2.12.2 | persone.js | la cache di 30 secondi dell'elenco persone valeva per il browser: chi entrava subito dopo un'altra persona poteva vedere l'elenco chiesto da lei. Ora si ricarica se cambia l'accesso. |
| FATTO 2.12.2 | api/certificati.py | (suggerimento) `_nome_file` rifaceva tre query per ogni attestato già caricati dall'elenco: ora riusa persona e corso. |
| FATTO 2.12.2 | api/dashboard_formazione.py, services/iscrizioni.py | (suggerimento) un conteggio dei posti per ogni sessione imminente: ora una query sola per tutte. L'endpoint non aveva test: aggiunto, insieme a quello che confronta il conteggio in blocco con quello a una a una. |

## PR #38 (2.12.3, questionari e copertine nella configurazione)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 2.12.3 | services/configurazione.py | importando una domanda con «obbligatoria» scritto come testo (per esempio «false») il valore veniva trasformato in «sì»: ora lo valuta la validazione, e un valore non valido fa saltare il questionario con un avviso |
| FATTO 2.12.3 | services/configurazione.py | il limite di domande valeva solo per quelle del file: aggiungendole a un questionario già pieno lo si superava. Ora si controlla il totale e le domande che non ci stanno sono segnalate negli avvisi |
| FATTO 2.12.3 | services/configurazione.py | se il corso aveva il codice di copertina giusto ma il file sul disco mancava, l'import non lo ripristinava: ora si salta solo se il file esiste davvero |
| FATTO 2.12.3 | tests/test_configurazione_questionari.py | un'asserzione con `and`/`or` poteva passare anche con il percorso della copertina ancora nel database: divisa in due. Aggiunti i test per file mancante, limite e «obbligatoria» non valida |
| FATTO 2.12.3 | services/configurazione.py | (fuori dal diff) importando domande già presenti in un ordine diverso, l'ordine nel questionario di destinazione non cambiava: ora le domande del file prendono il suo ordine e le altre restano in coda; la differenza compare nell'anteprima come «ordine» |
| FATTO 2.12.3 | services/configurazione.py | (fuori dal diff) «predefinito» scritto come testo (per esempio «false») contava come «sì»: ora un valore non booleano fa saltare il questionario con un avviso |
| FATTO 2.12.3 | services/configurazione.py | (fuori dal diff) un corso con «questionario» che non era un testo (un numero, un elenco) faceva fallire tutto l'import con errore 500: ora è un avviso e il corso resta com'è |
| FATTO 2.12.3 | services/configurazione.py | un questionario (o una domanda) del file che non era un oggetto, per esempio «null», faceva fallire l'import con errore 500: ora è un avviso e si passa al successivo |
