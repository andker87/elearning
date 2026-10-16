import os, platform, sys, time
from importlib import metadata
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..config import settings
from ..services import cifratura as c
from ..database import get_db
from ..models.azienda import Azienda
from ..version import APP_VERSION
from .deps import get_current_user
from ..models.user import UserRole

router = APIRouter(prefix="/api/about", tags=["about"])
_AVVIO = time.time()

PACCHETTI = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "python-jose", "httpx", "apscheduler",
             "reportlab", "openpyxl", "pywebpush", "psycopg2-binary"]

CHANGELOG = [
    {"version": "1.9.7", "date": "2026-10", "label": "Dati personali cifrati nel database", "changes": [
        "Nome ed email degli utenti, referente/email/telefono degli enti esterni, email, IP e dettaglio del registro attività sono cifrati nella colonna (AES-256-GCM, stessa chiave dei file): chi legge il database vede solo testo cifrato",
        "Per l'accesso e i controlli di unicità l'email ha un'impronta (HMAC con una chiave propria): l'email è la stessa senza badare alle maiuscole e due account non possono avere lo stesso indirizzo. Il registro filtra per email o IP interi; ordinamento e ricerca per nome si fanno nel programma",
        "Per gli eventi sugli utenti il nome dell'entità (l'email) passa nel dettaglio cifrato; gli accessi falliti registrano l'indirizzo digitato, così si cercano per email",
        "I dati esistenti si convertono con python -m app.cifratura_cli cifra (a lotti); la pagina Stato mostra quanti valori sono ancora in chiaro; ruota e decifra valgono anche per questi dati. Un confronto scritto per errore su una colonna cifrata dà un errore invece di non trovare nulla in silenzio",
        "docs/sicurezza.md elenca cosa è cifrato, cosa no e perché",
    ]},
    {"version": "1.9.6", "date": "2026-10", "label": "Strumenti di compilazione del sito: da Create React App a Vite", "changes": [
        "Il sito si compila con Vite al posto di Create React App (progetto abbandonato, con decine di vulnerabilità negli strumenti di compilazione): ora `npm audit` non segnala nulla, nemmeno sugli strumenti di compilazione, e il controllo è diventato bloccante nella CI e nello script",
        "Nessuna modifica per chi usa la piattaforma: provate in un browser vero tutte le 32 pagine, il service worker e il manifest; i file del sito hanno ora il nome che cambia a ogni versione nella cartella /assets",
        "File con interfaccia rinominati da .js a .jsx (richiesto da Vite)",
    ]},
    {"version": "1.9.5", "date": "2026-10", "label": "Dipendenze, immagini e controlli di sicurezza", "changes": [
        "Token di accesso e di riproduzione con PyJWT al posto di python-jose (libreria non più mantenuta e con vulnerabilità senza correzione); accesso aziendale (SSO) portato sulla nuova libreria con gli stessi controlli (firma, emittente, destinatario, scadenza, nonce)",
        "Il sito è servito da nginx senza privilegi invece che da Node; le immagini hanno gli aggiornamenti di sicurezza di sistema e non contengono più pip, setuptools e wheel: l'analisi delle immagini (Trivy) non trova vulnerabilità alte o critiche",
        "Aggiunto package-lock.json del sito e installazione con npm ci: le versioni delle librerie sono fisse e le build riproducibili; le librerie incluse nel sito non hanno vulnerabilità note",
        "Se la chiave di cifratura manca o il file è alterato, l'emissione di un attestato o di un'esportazione con il logo si ferma con un errore chiaro invece di produrre un documento senza logo",
        "Estensione del file video ripulita; header di sicurezza del browser (nosniff, anti-incorniciamento, referrer, permessi)",
        "Corretta una svista della 1.9.4: il sito non si ricompilava (un commento di configurazione ne bloccava la build)",
        "Nuovo scripts/controlli-sicurezza.sh e flusso GitHub Actions (test, Bandit, pip-audit, npm audit, Trivy) a ogni modifica",
    ]},
    {"version": "1.9.4", "date": "2026-10", "label": "Video in più qualità e cifrati", "changes": [
        "Ogni video viene convertito in più qualità (480p, 720p, 1080p, 4K) fino a quella del file caricato, mai ingrandendo; configurabile con VIDEO_ALTEZZE. Il video è guardabile appena c'è la prima qualità, le più alte arrivano dopo",
        "Il player sceglie da solo la qualità adatta allo schermo e alla rete (prudente se il browser non dà informazioni sulla rete) e lascia scegliere a mano; la scelta si ricorda. Una qualità più bassa pesa meno sulla rete, utile da remoto",
        "Video e sottotitoli cifrati su disco; si decifrano al volo a blocchi, quindi si può saltare avanti e indietro scaricando solo ciò che serve",
        "Il file originale caricato viene eliminato a fine conversione (resta in chiaro solo il tempo necessario); al riavvio i video rimasti a metà vengono recuperati e gli originali in chiaro ripuliti",
        "Una conversione alla volta, per non appesantire il server; nginx non accumula i video su disco durante la riproduzione",
        "Lo strumento da riga di comando cifra anche i video già presenti, escludendo i file temporanei della conversione",
    ]},
    {"version": "1.9.3", "date": "2026-10", "label": "Cifratura dei file e dei segreti", "changes": [
        "File cifrati su disco (AES-256-GCM, a blocchi): attestati emessi e caricati, template, informativa, logo e icona; si decifrano solo al momento dell'uso, con i controlli di accesso di prima",
        "Chiave da ambiente (CHIAVE_CIFRATURA): senza, la piattaforma funziona ma l'Admin tecnico vede un avviso discreto; con CIFRATURA_OBBLIGATORIA non si avvia. Se la chiave è sbagliata o manca dopo l'attivazione, la piattaforma si ferma con un messaggio chiaro invece di scrivere dati illeggibili",
        "Strumento da riga di comando (python -m app.cifratura_cli): genera-chiave, stato, cifra, decifra, ruota (cambio chiave), disattiva",
        "Chiave privata delle notifiche push cifrata nel database",
        "Link del calendario: nel database resta solo l'impronta, il link si vede una sola volta alla creazione (poi si può crearne uno nuovo)",
        "Caricamento degli attestati esterni scritto a pezzi con limite di 25 MB",
        "Nuovo documento docs/sicurezza.md: che cosa è protetto, gestione e perdita della chiave, rotazione, responsabilità di chi installa",
    ]},
    {"version": "1.9.2", "date": "2026-10", "label": "Pagina Informazioni ridotta per gli utenti", "changes": [
        "Gli utenti comuni e l'Ufficio Formazione vedono solo nome della piattaforma, azienda e versione; novità tecniche, ambiente, librerie e integrazioni sono visibili solo all'Admin tecnico",
    ]},
    {"version": "1.9.1", "date": "2026-10", "label": "Registro attività gestibile", "changes": [
        "Audit log: di default si vedono solo gli eventi importanti; accessi riusciti e attività di routine si vedono scegliendo «Tutti» (anche nelle esportazioni)",
        "Riepilogo in cima alla pagina: eventi, accessi, accessi falliti e account bloccati nelle ultime 24 ore, 7 e 30 giorni, più lo stato della manutenzione",
        "Conservazione configurabile (AUDIT_RETENZIONE_MESI, 24 mesi di default): ogni notte gli eventi più vecchi vengono cancellati e la pulizia lascia una traccia nel registro",
        "Esportazione giornaliera facoltativa (AUDIT_EXPORT_DIR): un file .ndjson per giorno da far prelevare a un sistema di gestione dei log; con l'esportazione attiva si cancella solo ciò che è già stato esportato (i giorni esportati sono registrati nel database, quindi il collettore può spostare o cancellare i file)",
        "Copia in tempo reale facoltativa sull'output del container (AUDIT_LOG_STDOUT), emessa solo dopo il salvataggio dell'evento",
        "Indici sul registro per mantenere veloci ricerche e filtri con molti eventi",
    ]},
    {"version": "1.9.0", "date": "2026-10", "label": "Video protetti, CORS chiuso, upload a pezzi", "changes": [
        "Video: non più in una cartella pubblica; ogni riproduzione usa un indirizzo a tempo (2 ore) richiesto da chi ha diritto (iscritto alla sessione, Ufficio Formazione, Admin tecnico); sottotitoli protetti allo stesso modo; il player ne chiede di nuovi quando scadono",
        "L'elenco dei video e i percorsi dei file sul server non sono più visibili agli utenti comuni",
        "CORS: nessun sito esterno ammesso di default, senza bisogno di configurare l'indirizzo pubblico; eccezioni solo da ambiente (CORS_ORIGINS)",
        "Caricamento di video e sottotitoli scritto su disco a pezzi, con limite di dimensione (2 GB e 2 MB); un caricamento fallito non lascia file parziali né rovina quello precedente",
        "Documentazione: tolti i riferimenti a strumenti e progetti specifici; la piattaforma è generica",
    ]},
    {"version": "1.8.7", "date": "2026-10", "label": "Documenti e rifiniture (rilievi della revisione pubblica)", "changes": [
        "Documentazione: il README indica l'indirizzo HTTPS pubblico e di non esporre direttamente la porta 2018; la guida dell'amministratore riporta le regole complete della password; la roadmap elenca i ruoli fissi corretti",
        "Chiusa la serie di revisioni della cronologia pubblicata: tutti i rilievi di CodeRabbit sono stati verificati e corretti oppure chiusi con motivazione (registro in docs/rilievi-coderabbit.md)",
    ]},
    {"version": "1.8.6", "date": "2026-10", "label": "Interfaccia (rilievi della revisione pubblica)", "changes": [
        "Errori sempre visibili: sessioni del responsabile, richieste di corso, dashboard formazione (sollecito), azienda, piattaforma, template attestati, fabbisogno, dettaglio sessione, corsi, informativa e impostazioni utente mostrano il motivo quando un'operazione o un caricamento falliscono (anche a server irraggiungibile), con «Riprova» dove serve; gli errori di validazione non appaiono più come testo grezzo",
        "Tastiera e accessibilità: stelle del gradimento, intestazioni ordinabili, schede (impostazioni, KPI, fabbisogno) e dettaglio dell'audit si usano anche senza mouse",
        "Risposte vecchie scartate: audit, matrice formativa, richieste formative e albero di provenienza non mostrano più il risultato di una richiesta superata dai filtri nuovi",
        "Template attestati: durante il trascinamento di un campo non si perdono più le modifiche fatte nel frattempo; «predefinito» non ricarica i campi in modifica",
        "Banner di installazione e notifiche: restano visibili se l'operazione fallisce (con il motivo) e l'installazione rifiutata non li nasconde per sempre; se il server non salva l'attivazione push, il browser torna coerente",
        "Etichette: i moduli di rinomina e unione si chiudono solo se l'operazione riesce. Fabbisogno: righe del modulo con chiave stabile; «Azzera» mantiene la campagna da cui si arriva. Notifiche push: l'indirizzo da aprire deve essere della piattaforma",
    ]},
    {"version": "1.8.5", "date": "2026-10", "label": "Correttezza e prestazioni (rilievi della revisione pubblica)", "changes": [
        "Rinnovo automatico: tiene conto della scadenza breve dopo un test non superato, e un'iscrizione a una sessione già iniziata o in bozza non blocca più il rinnovo",
        "Dati in ingresso: richieste di corso, filtri per etichetta, template degli attestati e icona controllano forma e dimensione prima di salvare; un identificativo sbagliato dà un errore chiaro invece di un errore del server; un'immagine non valida non sostituisce più quella buona",
        "Esportazioni: l'audit dichiara quando il file è troncato, l'apice anti-formula resta solo in CSV ed Excel (non nei PDF), l'ordinamento è stabile e il filtro «fine» con orario è preciso",
        "Pacchetto ispezione: il limite conta i file realmente presenti e le ricerche dei documenti sono due in tutto, non due per riga",
        "Notifiche: il sollecito manuale non blocca la richiesta e non si perde se l'invio fallisce; push senza duplicati sull'iscrizione ripetuta; nessun invito calendario per sessioni in bozza; nome dell'allegato email ripulito; errori inattesi dell'accesso aziendale riportano alla pagina di accesso",
        "Dashboard formazione: i conteggi usano le stesse persone (attive) con e senza filtro per ufficio; le sessioni senza data non rompono il confronto. Pagina di salute: regge anche se manca la cartella dei video",
        "Interno: Pillow aggiornato (12.3.0), registro dei log al posto di print, il calendario personale fa meno query, l'importazione CSV degli utenti non blocca più il server, migrazioni con rollback prima dello sblocco",
        "Esportazione dati personali: tolto il contatore interno di sessione (token_version). Dalla review della 1.8.4: il pulsante «Apri l'informativa in PDF» non funzionava (import mancante); l'impronta del piano Entra comprende ora anche nomi e date; la migrazione dei doppioni tiene l'invito più avanzato",
    ]},
    {"version": "1.8.4", "date": "2026-10", "label": "Sicurezza e integrità dei dati (rilievi della revisione pubblica)", "changes": [
        "File caricati: attestati, allegati, template e informativa non sono più raggiungibili senza accesso; restano pubblici solo logo e icona. L'informativa PDF e lo sfondo dei template si aprono dall'interno della piattaforma. Il nome dei file allegati agli attestati esterni non può più contenere percorsi",
        "Accesso aziendale: senza indirizzo email nel token si usa il nome utente solo se l'emittente è il tenant Entra dichiarato nel token",
        "Reset password: la richiesta manuale si rifiuta per account disattivati o con credenziali aziendali; il link non si può riscattare due volte in parallelo",
        "Doppioni impossibili anche con richieste in parallelo: una persona per sessione, un gradimento per iscrizione, un invito per ufficio e campagna, una persona per richiesta di corso; l'ultimo posto di una sessione non si assegna due volte. Le campagne chiuse non accettano più deleghe né risposte",
        "Sincronizzazione Entra: si applica solo il piano visto in anteprima (se cambia nel frattempo bisogna rifare l'anteprima) e non si possono disattivare tutti gli utenti in ambito in un colpo solo",
        "Test: il formatore gestisce il test solo con una sessione pianificata o in corso. Importazione configurazione: un ufficio nullo nel file non cancella quello esistente. Offboarding: i posti liberati non contano chi era in lista d'attesa",
    ]},
    {"version": "1.8.3", "date": "2026-10", "label": "Correzioni dalla quarta revisione del codice", "changes": [
        "Utenti: non si può più cambiare il ruolo di sé stessi né dell'ultimo Admin tecnico attivo (la piattaforma non resta senza amministratori)",
        "Auto-iscrizione: possibile solo in sessioni pianificate o in corso, anche all'approvazione del responsabile",
        "Password dimenticata e inviti da import CSV: le email partono in sottofondo e solo a salvataggio riuscito (nessuna differenza di tempi tra account esistenti e no, nessun link morto)",
        "Esportazioni CSV/Excel: i testi che iniziano con = + - @ vengono neutralizzati (niente formule iniettate da nomi o commenti)",
        "Test: il formatore gestisce il test solo finché ha una sessione del corso ancora aperta e può vedere le risposte corrette",
        "Sincronizzazione Entra: il freno di sicurezza non permette di disattivare più della metà degli utenti in ambito (minimo 2), anche su installazioni piccole",
        "Importazione configurazione: i gruppi di sistema non si toccano e i campi assenti nel file non cancellano quelli esistenti",
        "Accesso: un login sbagliato mostra il messaggio d'errore invece di ricaricare la pagina",
    ]},
    {"version": "1.8.2", "date": "2026-10", "label": "Correzioni dalla terza revisione del codice", "changes": [
        "Gruppi e uffici: non si può più creare un giro nella gerarchia (un ufficio sotto un suo sotto-ufficio), e le visite della gerarchia non si bloccano nemmeno con dati incoerenti",
        "Iscrizioni: oltre la capienza le persone in più vengono segnalate invece di far fallire tutta l'iscrizione, e non si supera mai il numero di posti; niente iscrizioni in sessioni chiuse o annullate (né in bozza per i responsabili); più posti o lista d'attesa attivata fanno salire subito chi aspetta, che riceve l'invito calendario anche dopo la disattivazione di un collega",
        "Sessioni: pianificare due volte non rimanda gli inviti e una sessione chiusa non torna pianificata",
        "Test: il formatore che modifica un test vede e conserva le risposte corrette; salvare un test con risposte non dà più errore",
        "Email e notifiche push partono in sottofondo dopo il salvataggio: una richiesta con centinaia di notifiche non si blocca, e niente invii per operazioni annullate",
        "CF-Connecting-IP si usa solo se dichiarato che davanti c'è Cloudflare (PROXY_CLOUDFLARE); logo verificato al caricamento e icona dell'app sempre disponibile",
    ]},
    {"version": "1.8.1", "date": "2026-10", "label": "Correzioni dalla seconda revisione del codice", "changes": [
        "Il limite di tentativi per indirizzo conta solo i login falliti: dietro un proxy che nasconde l'IP vero gli accessi riusciti non lo consumano; la sospensione di un account avvisa gli Admin tecnici senza inviare email durante il login",
        "Iscrizioni: non si annulla più uno storico già completato; chi era in lista d'attesa non libera un posto e nessuno viene promosso se non c'è un posto libero",
        "Disattivare un utente dal modulo fa lo stesso offboarding completo di import ed Entra (iscrizioni aperte, dispositivi, calendario); non si disattiva sé stessi né l'ultimo Admin tecnico",
        "Sincronizzazione Entra: una persona si riconosce da mail, UPN o alias, così non viene disattivata o duplicata se registrata qui con un indirizzo diverso",
        "Accesso aziendale compatibile anche con provider che includono at_hash (Google, Keycloak, Okta); variabili d'ambiente vuote trattate come non impostate (SMTP); oggetto delle email ripulito dagli a capo; memoria dei limiti di tentativi non più illimitata",
    ]},
    {"version": "1.8.0", "date": "2026-10", "label": "Pronta per la produzione: migrazioni, IP affidabili, inviti senza password", "changes": [
        "Lo schema del database si cambia con migrazioni numerate (Alembic): all'avvio vengono applicate da sole, una volta sola anche con più processi, e un database già in uso viene riconosciuto senza perdere nulla. Non si cancellano più colonne senza copiare i dati",
        "IP del client affidabile in qualsiasi installazione: gli header che lo indicano si credono solo se arrivano da un proxy dichiarato in PROXY_FIDUCIARI (reti separate da virgola); senza, vale l'indirizzo di chi si connette e nessun limite si aggira con header falsi",
        "I nuovi utenti ricevono per email un link, valido 3 giorni, per scegliere la propria password: nessuna password viaggia più per posta. Senza invio email l'amministratore vede una password temporanea una sola volta",
    ]},
    {"version": "1.7.2", "date": "2026-10", "label": "Correzioni dalla revisione del codice", "changes": [
        "Il link di reset password usa solo l'URL configurato, mai un indirizzo preso dalla richiesta; limite di richieste per ogni indirizzo email oltre a quello per IP",
        "L'import CSV dei cessati si sceglie esplicitamente (non più dal nome del file) e non disattiva gli Admin tecnici",
        "Accesso: stessa risposta per password sbagliata, email inesistente e account sospeso (non si può più capire se un indirizzo è registrato né se è bloccato), tempi pareggiati, sospensione segnalata agli Admin tecnici",
        "Il login e il reset ignorano maiuscole e minuscole nell'email; l'account Admin tecnico non si collega all'accesso aziendale per email",
        "Con una password assegnata da altri il server consente solo di cambiarla; il feed del calendario smette di funzionare per chi è disattivato; la struttura dei responsabili è visibile solo a sé stessi e alla Formazione",
    ]},
    {"version": "1.7.1", "date": "2026-10", "label": "Filtri per etichetta ovunque", "changes": [
        "Il filtro per etichetta è ora anche nella Dashboard KPI (con i suoi export), nella Dashboard Ufficio Formazione (indicatori, persone con problemi, sessioni imminenti), nell'elenco delle sessioni e nelle sessioni del responsabile; le sessioni mostrano le etichette del corso",
    ]},
    {"version": "1.7.0", "date": "2026-10", "label": "Etichette dei corsi", "changes": [
        "I corsi si classificano con etichette raggruppate in famiglie (Tematica, Riferimento normativo, Ambito, Obbligo), definite dall'Ufficio Formazione: scelta singola o multipla, famiglie obbligatorie, etichette da archiviare, rinominare o unire, avviso se «Trasversale» è scelta insieme a un cliente",
        "Registro formazione, matrice formativa, pacchetto per l'ispezione ed export si filtrano per etichetta: ad esempio tutto ciò che riguarda il D.Lgs 81/08 per un audit ISO 45001",
        "Il vecchio campo Categoria diventa una Tematica; il «motivo dell'obbligo» non è più sui percorsi ma sul corso (famiglia Obbligo). Le etichette viaggiano con l'esportazione della configurazione",
    ]},
    {"version": "1.6.0", "date": "2026-10", "label": "Fusione delle richieste e configurazione portabile", "changes": [
        "Fabbisogno formativo: chi valuta le richieste dei sotto-uffici può unire quelle simili in una sola, che sale al posto delle originali; le originali restano intatte e la provenienza (ufficio, autore, numeri, note) è sempre consultabile, anche dopo più unioni a livelli diversi. Chi ha scritto una richiesta viene avvisato e vede dove sta andando",
        "Valutazione delle richieste in blocco (approva o rifiuta più richieste insieme, con motivo) e richieste raggruppate per argomento; l'unione si può annullare finché nessuno sopra l'ha valutata",
        "Nuova pagina Configurazione: esporta in un file e importa dati aziendali, gruppi e uffici, società di formazione, corsi e percorsi, con anteprima prima di applicare e senza mai cancellare nulla. Restano fuori, per ora, persone, video, immagini, template, test e credenziali",
        "Esportazione in CSV, Excel e PDF anche di utenti, gruppi, società di formazione, catalogo corsi e percorsi",
    ]},
    {"version": "1.5.1", "date": "2026-10", "label": "Pagine a tutta larghezza", "changes": [
        "Su schermi larghi il contenuto delle pagine occupa tutto lo spazio accanto alla barra laterale, invece di fermarsi a circa tre quarti",
    ]},
    {"version": "1.5.0", "date": "2026-10", "label": "Rinnovo automatico dei corsi", "changes": [
        "Rinnovo automatico, opzione per corso dell'Ufficio Formazione (spenta di default, solo per corsi con validità): a ridosso della scadenza iscrive la persona alla prossima sessione utile, rispettando capienza e lista d'attesa, e avvisa persona e responsabile",
        "Se non c'è nessuna sessione disponibile avvisa la Formazione invece di non fare nulla; dalla tabella dei corsi si vede in anticipo chi verrebbe iscritto e a quale sessione",
    ]},
    {"version": "1.4.2", "date": "2026-10", "label": "Fabbisogno formativo: vista della Formazione", "changes": [
        "Pagina Fabbisogno formativo della Formazione in tre schede (Nuova campagna, Campagne, Richieste formative), con intestazioni cliccabili per ordinare e filtri",
        "Richieste formative pensate per molte campagne e centinaia di persone: vista per argomento (quante persone e da quali uffici, anche se scritto in modi diversi) con dettaglio a scomparsa, elenco dettagliato paginato, filtri per campagna, ufficio con sotto-uffici, periodo, stato e testo, export",
        "Una richiesta arrivata alla Formazione si chiama «Ricevuta» (non più «Approvata») e ha un colore blu informativo",
    ]},
    {"version": "1.4.1", "date": "2026-10", "label": "Fabbisogno formativo più chiaro", "changes": [
        "Fabbisogno formativo: una campagna compare una sola volta anche se guidi più uffici; per ogni ufficio due scelte spiegate (rispondo io / chiedo ai sotto-uffici) e lo stato resta visibile dopo la scelta",
        "Una risposta o una richiesta spontanea può contenere più esigenze, con il pulsante + per aggiungere righe; le note sono in fondo a ogni riga",
        "Le campagne aperte raggiungono anche gli uffici creati dopo il loro avvio; chi guida un ufficio vede le richieste anche da utente Formazione",
        "Menu: sezione «Fabbisogno formativo» con la voce «Richieste»; titoli dei riquadri tabella non più attaccati al bordo",
    ]},
    {"version": "1.4.0", "date": "2026-10", "label": "Sincronizzazione utenti e test automatici", "changes": [
        "Sincronizzazione utenti con Microsoft Entra ID (opzionale, da ambiente): anteprima delle modifiche, creazione di chi entra, disattivazione di chi esce con annullo delle iscrizioni aperte e promozione dalla lista d'attesa; giro notturno automatico facoltativo con freno di sicurezza",
        "L'import dei cessati da CSV applica la stessa disattivazione completa (iscrizioni aperte, dispositivi, sessioni) e segnala docenze e responsabilità da riassegnare",
        "Suite di test automatici (oltre 100) su accessi, permessi, registro e matrice, lista d'attesa, SSO, privacy, audit, pacchetto ispezione e sincronizzazione",
    ]},
    {"version": "1.3.0", "date": "2026-10", "label": "Accessi sicuri, matrice e pacchetto per l'ispezione", "changes": [
        "Accessi: password di almeno 14 caratteri con maiuscola, numero e carattere speciale; blocco dell'account per 15 minuti dopo 5 tentativi falliti e limite per indirizzo; cambio o reset della password chiude le altre sessioni",
        "Password dimenticata: link via email se l'invio è attivo, altrimenti richiesta all'Admin tecnico che assegna una password temporanea; al primo accesso con una password assegnata se ne sceglie una propria",
        "Matrice formativa: persone per corsi richiesti dai percorsi, con stato di ogni cella (valido, in scadenza, scaduto, da aggiornare, mancante...), percentuale in regola ed export",
        "Pacchetto per l'ispezione: ZIP con registro, matrice, attestati emessi e caricati e indice dei documenti, per azienda, ufficio o persona",
        "Su telefono le tabelle larghe scorrono in orizzontale invece di allargare la pagina",
    ]},
    {"version": "1.2.1", "date": "2026-10", "label": "Privacy come strumento aziendale", "changes": [
        "Informativa privacy caricabile dall'Admin tecnico (testo e/o PDF) e consultabile da ogni utente dal proprio profilo, senza accettazione al login",
        "Tolta la richiesta di cancellazione dei dati: la piattaforma è uno strumento aziendale e i dati di formazione si conservano per obbligo. Resta il download dei propri dati",
    ]},
    {"version": "1.2.0", "date": "2026-10", "label": "Uniformità di menu, impostazioni e privacy", "changes": [
        "Pagina Informazioni con versione e novità, pagina Piattaforma (nome, URL pubblico, icona dell'app) con manifest dell'app generato dalle impostazioni",
        "Tema chiaro/scuro, campanella delle notifiche nella barra laterale, impostazioni utente a schede, menu Amministrazione con sottomenu Impostazioni",
        "Privacy: ogni utente può scaricare i propri dati personali",
        "Audit log esportabile anche in Excel e PDF, con gli stessi filtri dell'elenco",
    ]},
    {"version": "1.1.0", "date": "2026-10", "label": "Accesso aziendale e audit esteso", "changes": [
        "Accesso aziendale (SSO, OpenID Connect) configurabile solo da ambiente; l'Admin tecnico entra sempre anche con password",
        "Audit delle azioni dei discenti: check-in, registro presenze, tentativi di test, avvio e completamento dei video. Il gradimento resta anonimo e non viene registrato",
        "Stato piattaforma (accessi, scheduler, SMTP, spazio) e Audit log con filtri, paginazione ed export",
    ]},
    {"version": "1.0.0", "date": "2026-10", "label": "Piattaforma completa", "changes": [
        "Catalogo corsi e percorsi, sessioni in cinque modalità, video con anti-skip, test, gradimento anonimo, attestati con template",
        "Dashboard Ufficio Formazione e KPI, registro formazione, gerarchia uffici/responsabili, fabbisogno formativo",
        "Notifiche in-app, email e push, app installabile, calendario (.ics e feed personale), comunicazioni alle sessioni, lista d'attesa, auto-iscrizione",
    ]},
]


@router.get("")
def about(db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = db.query(Azienda).first()
    dati = {
        "nome_piattaforma": (a.nome_piattaforma if a and a.nome_piattaforma else "E-Learning"),
        "nome_azienda": a.ragione_sociale if a else None,
        "url_pubblico": a.url_pubblico if a else None,
        "versione": APP_VERSION,
    }
    # Agli utenti solo nome e versione: novita' tecniche, ambiente, librerie e integrazioni sono dell'Admin tecnico.
    if user.role != UserRole.admin_tecnico:
        return dati
    dati["changelog"] = CHANGELOG

    versioni = {}
    for p in PACCHETTI:
        try:
            versioni[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pass
    dati["ambiente"] = {
        "python": sys.version.split()[0],
        "sistema": f"{platform.system()} {platform.release()}",
        "database": (db.execute(text("select version()")).scalar() or "").split(",")[0],
        "attivo_da_secondi": int(time.time() - _AVVIO),
        "fuso": os.environ.get("TZ") or time.tzname[0],
    }
    dati["dipendenze"] = versioni
    dati["cifratura"] = {"chiave_presente": c.attiva(), "obbligatoria": bool(settings.CIFRATURA_OBBLIGATORIA)}
    dati["integrazioni"] = {
        "smtp": bool(settings.smtp_enabled),
        "sso": bool(settings.sso_enabled),
        "microsoft_graph": bool(settings.graph_enabled),
        "notifiche_push": bool(a and a.vapid_public_key),
    }
    return dati
