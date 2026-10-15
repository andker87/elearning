# Rilievi di CodeRabbit da trattare (registro)

Registro unico dei commenti di CodeRabbit sulle PR della cronologia. Ogni rilievo è stato letto contro il codice **attuale** (1.8.3, non contro lo stato della fase recensita).
Le correzioni si fanno tutte insieme nella **1.8.4**, ultima PR della serie. Le PR di fase si fondono senza ritocchi.

Stato: `DA FARE` fondato · `VERIFICARE` probabile, da guardare nel codice prima · `CHIUSO` già a posto (con motivo) · `FATTO` corretto nella 1.8.4.

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
| DA FARE | api/certificato_templates.py | validare immagine e template_id prima di scrivere file; validare forma di `campi`; file temporaneo unico per l'anteprima |
| DA FARE | api/dashboard_kpi.py | ordinamento che fallisce se solo alcune sessioni hanno `data_inizio` |
| DA FARE | frontend/public/service-worker.js | validare l'URL della notifica (stessa origine) prima di aprirlo |
| DA FARE | frontend Gradimento.js | stelle non usabili da tastiera; passare i docenti della sessione al modulo |
| DA FARE | requirements.txt | Pillow 11.0.0 → versione più recente (verificare che esista la 12.3.0 indicata) |
| DA FARE | services/calendario.py | `_escape` non gestisce il ritorno a capo `\r` |
| DA FARE | services/email.py | ripulire `allegato_nome` nell'header Content-Disposition; gestire `submit` fallito nel hook after_commit |
| DA FARE | api/calendario.py | token calendario salvato in chiaro (consigliato: hash + confronto a tempo costante); query per sessione in un'unica query |
| DA FARE | api/richieste_corso.py | bloccare nuova valutazione di richieste già decise; validare `persone_ids` e `corso_id` (UUID), rifiutare `argomento` vuoto; N+1 in `_serialize` |
| DA FARE | api/fabbisogno.py | rifiutare deleghe e risposte a campagna chiusa; `_Contesto` carica tutto a ogni chiamata |
| DA FARE | api/dashboard_formazione.py | ambiti ufficio e senza filtro contano popolazioni diverse; commit della notifica prima di email e push |
| FATTO 1.8.4 | api/autoiscrizione.py | gestire sessione mancante in `approva` (già coperto in 1.8.3 per lo stato; verificare il caso 404) |
| DA FARE | api/gradimenti.py | validare `docente_id` e intervallo dei voti; query per docente/riga |
| DA FARE | services/certificati.py | valori di campo non validi in `genera_pdf_da_template` |
| DA FARE | services/push.py, api/push.py | `print` per i fallimenti; `invia_push` blocca la richiesta e fa commit a metà; corsa su `endpoint` nella sottoscrizione; `py-vapid` mancante dai requirements |
| DA FARE | frontend (varie) | gestione errori: SessioniResponsabile, RichiesteCorsoAdmin, RichiestaCorso, DashboardFormazione (sollecito), Azienda (rimuoviLogo), TemplateAttestati; banner PWA e notifiche che si nascondono dopo un fallimento; `push.js` annullamento a metà; stale closure in TemplateAttestati |

## PR #2 — fase 1.1.0

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | services/sso.py | collega l'account usando `preferred_username`/`upn` se manca `email`: richiedere un'email verificata (rilievo più importante) |
| DA FARE | api/admin_tecnico.py | esportazione audit troncata in silenzio (50.000 righe CSV/Excel, 2.000 PDF): renderlo esplicito; ordinamento con spareggio unico; filtro "fine" che aggiunge un giorno a un datetime; salute senza storage che fallisce |
| DA FARE | api/auth.py | import CSV in `async def` che blocca il server: usare un handler sincrono |
| DA FARE | api/azienda.py | icona pubblica senza limiti di elaborazione; decodificare l'icona prima di sostituire il file esistente |
| VERIFICARE | api/azienda.py | nuovi campi della società nel mapping `Azienda` |
| VERIFICARE | api/evidenze.py | presenza Teams e relativo audit nello stesso commit |
| VERIFICARE | api/test.py | domande conservate per tentativi già in corso |
| VERIFICARE | api/video.py | soglia di completamento (80%) uguale a quella dell'evento di audit |
| DA FARE | frontend AuditLog.js | richieste vecchie che sostituiscono i risultati attuali; dettagli non accessibili da tastiera |
| DA FARE | frontend Login.js | token SSO in `localStorage` (valutare alternativa) |
| DA FARE | frontend Utenti.js | testo d'aiuto CSV (ora si manda un link, non la password); endpoint di esportazione utenti |
| DA FARE | frontend Corsi.js, EdizioneDetail.js, StatoPiattaforma.js | gestione errori, array di validazione mostrato grezzo, tentativo di nuovo caricamento |
| DA FARE | api/sso.py | gestire errori inattesi nella callback |
| DA FARE | api/edizioni.py | non mandare inviti calendario per sessioni in bozza |
| CHIUSO | api/auth.py | inviti CSV dopo il commit: corretto nella 1.8.3 |

## PR #3 — fasi 1.2.0, 1.2.1 e 1.3.0 (12 commenti in linea, tutti minori, + 3 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| CHIUSO | api/password_reset.py | email di reset durante la richiesta: già in sottofondo dalla 1.8.3 |
| FATTO 1.8.4 | api/password_reset.py | `genera` non rifiuta richieste di account disattivati o non locali (verificato nel codice: manca il controllo) |
| FATTO 1.8.4 | api/privacy.py | il PDF dell'informativa è servito da `/uploads/...` senza autenticazione: servirlo da un endpoint con login (verificato) |
| DA FARE | api/matrice_ispezione.py | il conteggio documenti (limite pacchetto) avviene prima di verificare che i file esistano (verificato); righe storiche del pacchetto senza perimetro; ZIP costruito in modo sincrono senza limite su PDF/Excel; N+1 sulle righe del registro; verificare il BOM nell'`indice_documenti.csv` |
| DA FARE | frontend ImpostazioniUtente.js | errori non gestiti (informativa, esportazione dati, URL calendario); schede non usabili da tastiera |
| DA FARE | frontend InformativaPrivacy.js | errore di caricamento iniziale non gestito |
| DA FARE | frontend MatriceFormativa.js | richiesta fallita e risposte vecchie che sovrascrivono le nuove |
| DA FARE | frontend Piattaforma.js | errori in `rimuoviIcona` |

## PR #4 — fasi 1.4.0, 1.4.1 e 1.4.2 (9 commenti in linea)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | api/entra_sync.py | `applica` ricalcola il piano da Entra invece di applicare quello visto in anteprima (verificato): legare l'applicazione all'anteprima (impronta del piano) |
| FATTO 1.8.4 | services/offboarding.py | `posti_liberati` conta anche chi era in lista d'attesa (verificato); promozione dalla lista d'attesa legata al flag della sessione: rivedere il caso con lista disabilitata |
| DA FARE | tests/conftest.py | l'URL del database si scompone con `rpartition("/")`: usare il parser di SQLAlchemy (regge password e parametri con "/") |
| DA FARE | tests/test_privacy.py | l'asserzione sull'esportazione dati non controlla `token_version` |
| DA FARE | frontend Ordinabile.js | l'ordinamento per colonna non è azionabile da tastiera |
| DA FARE | frontend Fabbisogno.js | chiave stabile per le righe rimovibili del modulo; errori non gestiti in `delega` |
| DA FARE | frontend FabbisognoAdmin.js | errori nella creazione campagna non mostrati; "Azzera" non coerente con il contesto della campagna |

## PR #5 — fasi 1.5.0, 1.5.1 e 1.6.0 (6 commenti in linea + 1 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| DA FARE | services/rinnovo.py | `ripeti_entro` (test non superato) può fissare una scadenza più vicina di quella del corso e ora viene ignorata (verificato: il campo esiste e le notifiche lo usano, il rinnovo no) |
| DA FARE | services/rinnovo.py | un'iscrizione aperta a una sessione non più utilizzabile (già iniziata, ferma) blocca il rinnovo della persona (verificato: il controllo `gia_iscritto` conta anche sessioni passate e bozze) |
| CHIUSO | services/configurazione.py | un gruppo senza `percorso` nel file importato manda in errore l'ordinamento: segnalarlo o saltarlo con avviso (verificato) | — già rifiutato con errore 400 che nomina il campo (c'è il test)
| DA FARE | frontend AlberoOrigine.js | l'albero mostrato non è legato all'`id`: si aggiorna male cambiando richiesta |
| DA FARE | frontend Configurazione.js | `r.sezioni[k]` senza controllo se manca la chiave |
| DA FARE | docs/brief-video-formativi.md | chiarire quale voce va verificata (riga 53) e aggiornare il percorso di avvio di Copilot in Clipchamp (riga 30) |

## PR #6 — fasi 1.7.0, 1.7.1 e 1.7.2 (4 commenti in linea + 1 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| DA FARE | api/etichette.py, services/etichette.py | identificativi delle etichette non UUID nei filtri (`etichette=...`) arrivano al DB e danno errore 500: validarli prima (verificato: nessun controllo) |
| DA FARE | services/etichette.py | la migrazione delle categorie in etichette Tematica può creare duplicati (nome troncato a 80 caratteri ma cercato per esteso) e violare `uq_etichetta_famiglia_nome` (verificato nel codice) |
| DA FARE | frontend Etichette.js | `chiama` nasconde gli errori: i moduli di rinomina e unione si chiudono anche se la richiesta fallisce |
| FATTO 1.8.4 | api/password_reset.py + test | il riscatto del token di reset non è protetto da una corsa: due richieste in parallelo possono usarlo entrambe (verificato: nessun blocco della riga); aggiungere blocco e un test di copertura |

## PR #7 — fasi 1.8.0, 1.8.1, 1.8.2 e storico (5 commenti in linea + 5 di rifinitura)

| Stato | File | Rilievo |
|---|---|---|
| DA FARE | app/schema_legacy.py | `porta_a_baseline` usa `Base.metadata.create_all` con i modelli di OGGI: per un database precedente alle migrazioni, quando arriveranno migrazioni 0002+ lo schema "0001" non sarebbe più quello di partenza (verificato nel codice). Congelare lo schema 0001 (rilievo più importante di questa PR) |
| DA FARE | app/migrazioni.py | dopo un errore la transazione è interrotta e lo sblocco `pg_advisory_unlock` fallisce: fare rollback prima di rilasciare il blocco (verificato) |
| DA FARE | services/inviti.py | normalizzare `SSO_PUBLIC_URL` (spazi, barre finali) prima di usarlo come alternativa (verificato: solo `rstrip("/")`) |
| DA FARE | README.md | indicare l'URL HTTPS pubblico e limitare l'accesso diretto alla porta 2018 (documentazione; la parte di rete è infrastruttura dell'utente: solo testo) |
| DA FARE | ROADMAP.md (riga 10) | cita ancora i "Formatori" tra i ruoli di sistema (verificato): i ruoli fissi sono Admin tecnico, Ufficio Formazione e Utenti |
| DA FARE | docs/guida-amministratore.md, guida-utente.md | allineare le regole della password nelle due guide (la politica è: 14 caratteri, maiuscola, numero, carattere speciale) |
| DA FARE | scripts/modo-revisione.sh | togliere il file indice temporaneo anche in caso di errore |
| DA FARE | tests/test_revisione2.py, test_revisione3.py | asserzioni mancanti: successo dell'annullamento da lista d'attesa e dell'aggiornamento del test; validare la risposta di riserva come PNG |

## PR #8 — fase 1.8.3 (6 commenti in linea: sono sulle mie correzioni della quarta revisione)

| Stato | File | Rilievo |
|---|---|---|
| FATTO 1.8.4 | api/auth.py (import CSV) | `email_inviata` risulta vera anche se l'invio è solo programmato: se poi l'email fallisce, l'admin non vede mai la password temporanea (verificato: `inviata = bool(link)`). Segnalare "invito programmato" e dare un modo di recupero |
| FATTO 1.8.4 | api/test.py | il formatore di una sessione in **bozza** ha ancora accesso al test e alle risposte corrette: escludere anche le bozze (verificato: il filtro toglie solo chiuse e annullate) |
| FATTO 1.8.4 | services/configurazione.py | `is_ufficio` nullo nel file importato diventa `False` e cancella l'ufficio esistente (verificato: `bool(d["ufficio"])`); trattarlo come campo assente |
| FATTO 1.8.4 | services/entra_sync.py | con meno di 4 utenti in ambito il minimo di 2 lascia passare tutte le disattivazioni (verificato: 2 su 2, 2 su 3): il freno deve valere per ogni dimensione |
| FATTO 1.8.4 | services/export.py | l'apice di neutralizzazione compare anche nelle celle dei PDF: applicarla solo a CSV ed Excel |
| VERIFICARE | services/export.py | testi che iniziano con un ritorno a capo o spazi prima del `=`: probabilmente innocui (in un campo tra virgolette restano testo), da provare in Excel/LibreOffice prima di cambiare |

## Le prossime PR
Aggiungere qui sotto una sezione per ogni PR, appena arriva la review della fase.
