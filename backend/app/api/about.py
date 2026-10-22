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

router = APIRouter(prefix="/api/about", tags=["about"])
_AVVIO = time.time()

PACCHETTI = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "pyjwt", "httpx", "apscheduler",
             "reportlab", "openpyxl", "pywebpush", "psycopg2-binary"]

CHANGELOG = [
    {"version": "2.10.0", "date": "2026-10", "label": "Percorsi che iscrivono", "changes": [
        "Percorsi: pagina rifatta con schede «Elenco» e «Nuovo percorso». Ogni percorso ha una modalità: libero (nessun vincolo), sequenziale (uno dopo l'altro nell'ordine dei numeri, senza poter saltare) o con propedeuticità (per ogni corso si spuntano i corsi che deve aver già completato, al posto del campo di testo di prima). Si controllano i corsi ripetuti, gli ordini uguali e le propedeuticità che si richiamano a vicenda. I percorsi che avevano già dei prerequisiti diventano «con propedeuticità»",
        "Assegnare un percorso: dal pulsante «Persone» del percorso, con ricerca per nome o email, filtri per ufficio e mansione e selezione di singoli o di tutti i risultati. Chi lo riceve viene avvisato e iscritto subito ai corsi già sbloccati; gli altri a mano a mano che completa i precedenti (per un video, alla fine del video; per le altre sessioni, alla chiusura). Anche i percorsi con assegnazione automatica (ingresso, ufficio, mansione) iscrivono. Lo stesso elenco mostra chi ha il percorso, a che punto è su ogni corso, e permette di togliergli il percorso (le iscrizioni già fatte restano)",
        "Quale sessione: per ogni corso il sistema sceglie prima il video sempre disponibile, poi un video con data già iniziato, poi la sessione con la data più vicina che abbia posti (come il rinnovo automatico). Se tutte sono piene la persona aspetta. Se il corso non ha nessuna sessione, il corso resta «in attesa di una sessione» nel percorso, la Formazione riceve un avviso (una volta a settimana) e, appena viene pubblicata una sessione di quel corso, chi aspettava viene iscritto da solo. Se la persona annulla una sessione non le viene riproposta la stessa. Chi aveva già completato un corso, anche prima del percorso, lo ha fatto; chi non lo ha completato risulta «da rifare» e lo iscrive la Formazione. Un giro notturno ripassa tutto",
        "Corsi bloccati: un corso di un percorso con prerequisiti non completati non si può anticipare né da soli né tramite il responsabile (messaggio «Prima completa…», lucchetto nel Catalogo e in «I miei corsi»); la Formazione può iscrivere comunque. Un corso fuori dai percorsi della persona non è mai bloccato",
        "Spostare una persona: la Formazione può spostare un'iscrizione su un'altra sessione dello stesso corso, dalla pagina della sessione (colonna dei discenti) o dall'elenco di chi ha il percorso. Se la nuova sessione non può accoglierla non cambia niente; il posto lasciato si libera (e chi era in lista d'attesa sale); la persona è avvisata",
        "«I miei corsi»: nei percorsi ogni corso mostra il suo stato (completato, iscritto con la data, lista d'attesa, in attesa di una sessione, bloccato con ciò che manca, da rifare) e il collegamento alla sessione",
        "Privacy: lo stato di un percorso di una persona lo vedono lei, la Formazione e chi la guida; prima era leggibile da qualunque utente",
    ]},
    {"version": "2.9.0", "date": "2026-10", "label": "Come si accede e quando è disponibile", "changes": [
        "Iscrizione da parte della persona, con un solo menu nella scheda del corso: no (la Formazione iscrive), liberamente, con l'approvazione del suo responsabile, con l'approvazione della Formazione. Se serve il responsabile e la persona non ne ha uno, la richiesta va alla Formazione (prima la persona veniva iscritta senza chiedere a nessuno). Le richieste alla Formazione compaiono in «Richieste di iscrizione» come «richiesta dalla persona stessa» e chi ha chiesto riceve l'esito. Le altre vie restano: la Formazione iscrive, il responsabile iscrive il team direttamente o chiedendo l'iscrizione",
        "Video con data: si apre dall'ora di inizio (prima la sessione mostra «disponibile dal…», anche se sei già iscritto) e, se indicata, fino alla data di fine; senza data di fine resta disponibile finché la Formazione non chiude. Il blocco vale sul server, non solo nella pagina. Chi guarda il video fino alla soglia (e supera il test finale, se c'è) riceve l'attestato in automatico, come per i video sempre disponibili; le sessioni in presenza, ibride e remote si chiudono ancora a mano",
        "Una sessione passata la data di fine e ancora aperta è segnalata «da chiudere» nell'elenco e nella sua pagina: il sistema non la chiude da solo, così nessun esito cambia senza che la Formazione lo veda. Un video con la sola data di inizio non risulta più «finito» il giorno stesso e resta nel Catalogo",
        "Corretto alla chiusura di una sessione: chi aveva già completato (un video lo fa da solo) non riceve un secondo attestato, e le iscrizioni annullate o in lista d'attesa non diventano più «non completato»",
    ]},
    {"version": "2.8.0", "date": "2026-10", "label": "Questionari di gradimento personalizzabili", "changes": [
        "Nuova pagina «Questionari di gradimento» (Ufficio Training): la Formazione decide quali domande aggiuntive fare, di tipo stelle (1-5), sì/no, scelta tra opzioni o testo libero, obbligatorie o no, con ordine modificabile. Restano sempre le domande fisse: voto complessivo del corso, commento e voto a ogni docente. I questionari hanno un nome; uno è il predefinito per tutti i corsi, e nella scheda del corso si può sceglierne un altro",
        "Chi ha completato un corso trova in fondo alla pagina il link «Compila il test di gradimento», che apre una finestra con il modulo (anonimo, una sola volta). Prima il modulo occupava la pagina e aveva domande fisse",
        "Report: nel riepilogo di una sessione e nel CSV dei gradimenti compaiono anche le risposte alle domande aggiuntive (media delle stelle, conteggi per sì/no e per scelta, testi liberi, sempre senza nome). Se la Formazione cambia il questionario, i report già fatti restano leggibili perché il testo della domanda si conserva con la risposta",
        "Corsi: la scelta di chi può iscriversi è raggruppata e più chiara. «Aperto a tutti» (auto-iscrizione, compare nel Catalogo) è separato da «i responsabili possono iscrivere il team» (direttamente o su richiesta); nella tabella le capsule dicono «aperto a tutti» o «su iscrizione», e «i responsabili iscrivono il team» (prima «aperto ai responsabili», che faceva pensare a un corso aperto a tutti)",
    ]},
    {"version": "2.7.4", "date": "2026-10", "label": "Il video al centro", "changes": [
        "Pagina di un corso video: il video è il protagonista, grande (formato 16:9, fino al 72% dell'altezza dello schermo) subito sotto il titolo e senza cornici; sotto ci sono le informazioni (descrizione, docenti), poi il test e il parere. Chi non è ancora iscritto trova al suo posto il pulsante «Inizia il corso»",
        "Catalogo: i corsi già completati vanno in una sezione «Già completati» in fondo, così in alto restano quelli da fare",
        "Il questionario di gradimento si chiama «Il tuo parere sul corso» (prima «Com'è andata?»): è sempre lo stesso, anonimo, e non conta per l'esito",
        "Video con blocco dei salti: un salto in avanti è ammesso solo fino a dove si è guardato davvero (prima si poteva avanzare con tanti piccoli salti), e cambiando corso l'avanzamento non si porta dietro quello del precedente",
        "Storico corsi: se un corso ha più attestati si vedono tutti, e se una delle due richieste fallisce lo si dice invece di mostrare «Caricamento» o «nessun attestato»; la pagina della sessione propone «Riprova» se non riesce a caricare l'iscrizione",
        "Sicurezza: libreria Pillow aggiornata alla 13.0.0 (corregge 8 vulnerabilità note)",
    ]},
    {"version": "2.7.3", "date": "2026-10", "label": "Storico corsi e attestati", "changes": [
        "Attestato: il file scaricato ha un nome che dice cos'è, nella forma Titolo-del-corso_Cognome_Nome_AAAA-MM-GG.pdf (la data è quella di emissione, la stessa stampata sull'attestato). Accenti e simboli sono tolti per non dare problemi su nessun sistema; il nome è quello di chi ha ottenuto l'attestato anche se lo scarica la Formazione",
        "Storico corsi: una sola tabella con colonne Corso, Modalità, Data, Durata, Esito, Emesso il, Codice verifica e, per ogni attestato, «Visualizza» (si apre nel browser) e «Scarica PDF». Prima c'erano due tabelle separate. I corsi non completati restano nell'elenco, senza attestato. Il layout del PDF non cambia",
    ]},
    {"version": "2.7.2", "date": "2026-10", "label": "Seguire un corso e gestirlo sono due cose", "changes": [
        "Pagina della sessione: due viste distinte. Chi segue il corso vede solo ciò che serve a seguirlo: titolo e descrizione, quando e dove, durata, docenti, il video, il test, la presenza, l'attestato e il gradimento. Gli strumenti di gestione (iscritti, docenti, Teams, comunicazioni, eliminazione, durata) li vede solo chi gestisce la sessione, cioè l'Ufficio Formazione e i docenti di quella sessione. Chi gestisce e apre un corso dal Catalogo o da «I miei corsi» lo trova come discente, con un rimando «Gestisci questa sessione»; dall'elenco Sessioni apre la vista di gestione",
        "Privacy: un collega non vede più chi è iscritto a una sessione né come sta andando. L'elenco degli iscritti lo ricevono solo l'Ufficio Formazione e i docenti della sessione; chiunque altro riceve soltanto la propria iscrizione. «Iscrivi una tua risorsa» non è più nella pagina della sessione: i responsabili lo fanno da «Il mio team» → Corsi disponibili",
        "Corretto: i video con il blocco dei salti in avanti si fermavano dopo 2-3 secondi e ripartivano da capo, in ciclo, per chi li guardava la prima volta; il limite si confrontava con l'ultimo avanzamento confermato dal server (ogni 4 secondi) invece che con quanto si era guardato davvero",
    ]},
    {"version": "2.7.1", "date": "2026-10", "label": "Eliminare i corsi, pubblicare le sessioni", "changes": [
        "Corsi: pulsante «Elimina» (solo per l'admin tecnico, non per l'Ufficio Formazione). Si può eliminare un corso solo se non ha lasciato tracce di formazione (nessuna iscrizione attiva o conclusa, nessun attestato, non è in un percorso né in una richiesta di corso): in quel caso una finestra spiega cosa verrà tolto (corso, sessioni vuote, test, iscrizioni annullate) e chiede di riscrivere il titolo. Altrimenti la finestra elenca i motivi e invita a disattivarlo, così resta lo storico. L'eliminazione è registrata nel registro attività",
        "Sessioni: «Pubblica» al posto di «Pianifica». Una sessione nasce in bozza (la prepari e la salvi) e si pubblica quando è pronta: dalla pagina della sessione, dall'elenco o con la casella «Pubblica subito» alla creazione. Una sessione pubblicata e senza iscritti si può riportare in bozza. Lo stato «Pianificata» si chiama ora «Pubblicata»",
        "Sessioni: «Elimina» (nell'elenco e nella pagina della sessione) per le sessioni create per errore. La Formazione elimina quelle senza iscritti; con persone iscritte solo l'admin tecnico, scrivendo ELIMINA. Mai una sessione chiusa o con attestati: sono lo storico",
        "Catalogo: una sessione «sempre disponibile» pubblicata compare per tutti anche se il corso non ha l'auto-iscrizione. Per ogni sessione la pagina dice se è visibile nel Catalogo e, se no, perché (in bozza, corso senza auto-iscrizione...). Una sessione video già creata si può rendere «sempre disponibile» dalla sua pagina",
        "Pagina della sessione: «Il mio check-in» (segna inizio e fine presenza) compare solo a chi è iscritto alla sessione, non più a chi la gestisce",
    ]},
    {"version": "2.7.0", "date": "2026-10", "label": "Catalogo e corsi sempre disponibili", "changes": [
        "Nuova pagina «Catalogo» per tutti: i corsi a cui ci si iscrive da soli (corsi con auto-iscrizione) divisi in «Sempre disponibili» e «Sessioni in programma», con ricerca, posti liberi e pulsante per iscriversi o chiedere l'iscrizione (se serve l'approvazione del responsabile). Le sessioni già finite, in bozza o di corsi non attivi non compaiono",
        "Sessioni «sempre disponibili» (solo modalità video): senza date né posti, la guarda chi vuole quando vuole. Chi raggiunge la soglia di visione del video (80%) e, se il corso ha un test finale, lo supera, risulta completato e riceve l'attestato subito, senza che la Formazione chiuda la sessione. Con la regola del corso «concludi comunque» un test non superato non blocca; con «rifai il corso» in queste sessioni si può sempre riprovare. Compare in «I miei corsi» tra i corsi che stai seguendo",
        "Pulsante «Pianifica e rendi disponibile» nella pagina di una sessione in bozza: finora l'interfaccia non permetteva di pianificare una sessione, che quindi non era iscrivibile da nessuno (né dal catalogo né da «Il mio team»)",
        "Corretto: alla chiusura di una sessione video, chi aveva guardato solo una piccola parte del video risultava comunque completato; ora conta la percentuale vista (soglia 80%)",
    ]},
    {"version": "2.6.0", "date": "2026-10", "label": "Il mio team e corsi chiusi o aperti", "changes": [
        "«Il mio team» (era «Le mie risorse», che mostrava tutte le sessioni della piattaforma): ora riguarda solo le persone che guidi, in quattro schede. Il mio team: gli uffici che guidi e i sottouffici ad albero, con persone, ruoli e mansioni, e per ciascuna la situazione formativa (sessioni, corsi svolti, scadenze). Formazione del team: solo le sessioni in cui sono iscritte persone del tuo team, con quando, dove, durata e modalità, per sessione o per persona. Corsi disponibili: le prossime sessioni dei corsi aperti. Richieste e approvazioni: le auto-iscrizioni da approvare e l'esito delle tue richieste",
        "Corsi chiusi o aperti: nel corso si sceglie «Come si iscrivono le persone»: solo la Formazione (predefinito dei corsi nuovi, il corso chiuso), i responsabili iscrivono direttamente le persone del loro team, oppure i responsabili chiedono l'iscrizione e la Formazione approva. La Formazione iscrive sempre. Chi aggiorna: i corsi esistenti restano «iscrizione diretta» (comportamento invariato)",
        "Richieste di iscrizione: nuova pagina per la Formazione con le richieste dei responsabili (persona, ufficio, corso, sessione, posti liberi): si approvano (la persona viene iscritta nel rispetto di posti e lista d'attesa) o si rifiutano con un motivo; chi ha chiesto riceve una notifica, e un'email se attiva; una nuova richiesta avvisa la Formazione",
        "Nella sessione, un responsabile vede la scheda «Iscrivi una tua risorsa» o «Chiedi l'iscrizione di una tua risorsa» secondo il corso, e non la vede se il corso è chiuso",
        "Controlli sulle richieste: non si chiede né si approva l'iscrizione a una sessione già finita o per una persona non più attiva (si rifiuta); due persone della Formazione sulla stessa richiesta non si pestano i piedi; un modo di iscrizione sconosciuto in un file di configurazione importato lascia il corso chiuso; la vista «Per persona» distingue gli omonimi",
    ]},
    {"version": "2.5.0", "date": "2026-10", "label": "Durata dei corsi e sessioni riorganizzate", "changes": [
        "Corsi: nuovo campo «Durata» (ore e minuti), visibile anche nell'elenco. La sessione la eredita; chi la organizza può forzarla per quella sessione (compare la capsula «modificata») o ripristinare quella del corso. Il vecchio campo «ore dichiarate» delle sessioni esterne è diventato la stessa durata (migrazione automatica: ore per 60 minuti)",
        "La durata va sull'attestato: segnaposto «Monte ore» (numero, es. 1,5) e nuovo «Durata» (testo, es. 4 ore e 30 minuti), anche nel layout predefinito; i report delle ore erogate usano la durata vera invece della stima dalle date. Alla chiusura della sessione la durata si congela: modificare poi il corso non cambia gli attestati già emessi",
        "Sessioni: schede «Elenco sessioni» e «Nuova sessione»; tabella con corso (e etichette), modalità, quando, durata, luogo, docenti, iscritti e stato a capsule; filtri per stato, modalità, corso, periodo e ricerca; ordinamento dalle intestazioni; pulsanti Apri e Duplica ben distanziati; creando una sessione si passa subito al suo dettaglio. Per le sessioni esterne si può indicare l'ente erogatore, e il pulsante «Imposta la fine in base alla durata» calcola l'orario di fine",
        "Pagina «Le mie sessioni» (docente): la sezione si chiama «Da svolgere» e nell'elenco dei docenti di una sessione si segna solo il co-docente (il docente principale non ha più l'etichetta «titolare»)",
        "Dettaglio della sessione: Docenti e Discenti sono sezioni separate. Docenti: elenco con ruolo (titolare o co-docente) e pulsante per toglierli, si scelgono tra chi ha la qualifica Docente e gli esterni. Discenti: pannello «Aggiungi discenti» con ricerca per nome o email, filtri per ufficio (sottouffici compresi) e mansione, scelta delle singole persone o di tutti i risultati, avviso se i posti non bastano e riepilogo di chi non è stato iscritto; la durata si vede e si modifica dal dettaglio",
    ]},
    {"version": "2.4.1", "date": "2026-10", "label": "Sezione Video a schede", "changes": [
        "Video: schede «Elenco video» e «Carica video». L'elenco è una tabella (titolo, stato, durata, qualità, sottotitoli sì/no, numero di capitoli, anti-skip, in quante sessioni è usato) e ogni video si apre sotto la riga per gestirne le proprietà",
        "Dal video aperto: cambiare il titolo, attivare o no l'anti-skip, vedere l'anteprima compatta, caricare, sostituire o eliminare i sottotitoli, aggiungere, modificare ed eliminare i capitoli (si scrivono in minuti:secondi, non più in secondi, con controllo che non superino la durata)",
        "Si può eliminare un video con i suoi file (qualità, originale, sottotitoli), ma solo se nessuna sessione lo usa e non è in elaborazione (neanche appena caricato o con altre qualità ancora in preparazione); l'eliminazione è registrata nel registro attività",
    ]},
    {"version": "2.4.0", "date": "2026-10", "label": "Etichette libere, corsi a schede, player compatto", "changes": [
        "Etichette dei corsi: il sistema non crea più nessuna famiglia preimpostata (tematica, norma, ambito, obbligo): le definisci tu da zero, e la pagina vuota spiega come. Chi aggiorna non perde nulla: le famiglie già presenti restano. Solo chi arriva dal vecchio campo Categoria trova una famiglia «Tematica» con quei testi",
        "Corsi: schede «Elenco corsi» e «Nuovo corso»; tabella più snella (titolo con le sue caratteristiche in capsule, etichette, validità, versione, stato); in fondo alla riga i pulsanti Modifica, Test e Nuova versione. «Modifica» apre sotto la riga un modulo completo, uguale a quello di creazione (titolo, descrizione, validità, attestato, etichette, rinnovo automatico con anteprima, test finale, auto-iscrizione, stato). Dalla pagina Corsi c'è il collegamento alla gestione delle etichette",
        "Il player dei video è un'anteprima compatta (al massimo 560 px di larghezza e circa 340 px di altezza, proporzioni rispettate) invece di occupare tutta la pagina",
        "Un docente assegnato a una sessione (anche senza il permesso Formazione) può ora vedere il video della sua sessione e l'anteprima; la conversione del vecchio campo Categoria in etichette funziona anche se esistono già altre famiglie e si svuota il campo una volta fatta (la famiglia «Tematica» si crea o si riusa senza toccare le altre)",
        "Corretto: un'iscrizione annullata continuava a comparire in «I miei corsi»; ora le iscrizioni annullate non sono più mie (restano nel registro attività) e chi è in lista d'attesa lo vede indicato",
        "Pagina della sessione: chi la gestisce (permesso Formazione o docente della sessione) non vede più il player come se stesse seguendo il corso, ma una scheda «Video collegato» con titolo, stato e durata, e il pulsante «Anteprima del video» (non conta come visione e non registra nessun avanzamento). Se è anche iscritto, «Segui il video come discente» apre il player vero; chi arriva da «I miei corsi» e dallo storico lo trova subito",
    ]},
    {"version": "2.3.4", "date": "2026-10", "label": "Ruoli a colpo d'occhio", "changes": [
        "Elenco utenti: i ruoli sono capsule colorate con lo stesso colore e lo stesso nome ovunque (Admin, Formazione, Docente, Esterno; Utente per chi non ha permessi). Passando il mouse si legge cosa può fare, c'è una legenda sopra la tabella e le stesse capsule compaiono nel modulo di modifica. La colonna Tipo è assorbita da Esterno e il filtro Permessi diventa Ruoli",
        "La qualifica «Formatore» si chiama ora «Docente» in tutta la piattaforma (etichette, messaggi, guide, colonna «docente» del CSV, menu); la vecchia colonna «formatore» nei file si accetta ancora. Nell'esportazione utenti la colonna Permessi diventa Ruoli",
    ]},
    {"version": "2.3.3", "date": "2026-10", "label": "Importazione da Excel con controllo prima", "changes": [
        "Importa da Excel (.xlsx) oltre che da CSV: il tipo di file si riconosce dal contenuto (un Excel salvato con estensione .csv funziona), si legge il foglio «Utenti», i CSV salvati da Excel in codifica Windows si leggono, il vecchio .xls e i file rotti ricevono un messaggio che spiega cosa fare",
        "Prima di importare il file viene controllato: una finestra mostra il riepilogo per persona (chi verrà creato, con quali avvisi, quali righe verranno scartate) e solo con «Importa comunque» si crea qualcosa; nel controllo non si crea niente e non parte nessuna email. Vale anche per «Disattiva cessati»",
        "Un ufficio o una mansione che non esistono, o un ufficio lasciato vuoto, non scartano più la riga: la persona viene creata senza e il riepilogo lo dice (uffici e mansioni non si creano mai da soli); restano scartate solo le righe inutilizzabili (email, nome o cognome mancanti, email già presente, esterno senza organizzazione, password o data non valide)",
        "Modelli scaricabili in Excel e CSV, generati con i nomi veri di uffici e mansioni del sistema; il modello Excel ha i fogli Istruzioni, Uffici e Mansioni e il menu a tendina per l'ufficio",
        "Dopo l'importazione si scarica il riepilogo dei problemi e si trovano le persone senza ufficio con il nuovo filtro «Senza ufficio» nell'elenco utenti",
        "La conferma vale solo per il risultato visto nel controllo: se nel frattempo qualcosa cambia (una persona creata o disattivata da altri, un ufficio o una mansione) l'importazione si ferma senza fare nulla e chiede di controllare di nuovo; durante l'importazione la finestra non si può chiudere; due uffici con lo stesso nome o percorso risultano ambigui invece di sceglierne uno a caso; un CSV malformato dà un messaggio chiaro",
    ]},
    {"version": "2.3.2", "date": "2026-10", "label": "Selettore colore e modifica sotto la riga", "changes": [
        "Colore di uffici e mansioni: quadrato ben visibile che apre il selettore del browser, codice esadecimale (#RRGGBB) da scrivere o incollare, colori pronti e anteprima dell'etichetta; le mansioni ora hanno il colore anche in modifica",
        "Uffici, mansioni e utenti: il modulo di modifica si apre subito sotto la riga della voce che si sta modificando, senza dover tornare in cima alla pagina",
        "Importa da CSV: la pagina spiega che uffici e mansioni vanno creati prima; una persona creata senza una mansione inesistente è segnalata come «creato, con avvisi»",
        "Corretto: l'invito email dell'importazione CSV partiva con il nome sbagliato per chi aveva delle mansioni; la sincronizzazione da Entra non annulla più una correzione di nome fatta a mano quando Entra manda solo il nome visualizzato; un ufficio usato da un percorso o dal fabbisogno non si elimina più per errore",
    ]},
    {"version": "2.3.1", "date": "2026-10", "label": "Uffici più facili da gestire", "changes": [
        "Uffici: la modifica permette di cambiare nome, descrizione, colore, responsabile, stato e posizione nella gerarchia (sottoufficio di un altro ufficio, oppure di primo livello); non si può spostare un ufficio sotto uno dei suoi sottouffici",
        "Gli uffici sono sempre in ordine alfabetico a ogni livello e scritti con il percorso intero (per esempio «Produzione / Linea 2») in tutte le tendine e nell'albero, così la gerarchia si legge anche nelle organizzazioni complesse",
        "Importa da CSV: due modelli da scaricare (nuovi utenti, disattiva cessati), con le colonne giuste e una riga di esempio",
        "Corretto: nelle pagine Fabbisogno, Matrice formativa, Registro formazione e dashboard il filtro per ufficio risultava vuoto dopo la 2.2.0",
    ]},
    {"version": "2.3.0", "date": "2026-10", "label": "Nome e cognome separati", "changes": [
        "Nome e cognome sono due campi: si mostrano entrambi nell'elenco utenti e si usano per cercare e per ordinare (gli elenchi sono in ordine di cognome, poi nome); cifrati nel database come gli altri dati personali",
        "L'importazione CSV usa le colonne nome e cognome al posto di full_name; la configurazione iniziale chiede i due campi",
        "Accesso aziendale e sincronizzazione da Entra usano nome e cognome dell'azienda quando ci sono, altrimenti dividono il nome intero",
        "Chi aggiorna: le persone esistenti sono divise con una regola semplice (la prima parola è il nome, il resto il cognome, per esempio «Maria Grazia Rossi» diventa Maria / Grazia Rossi): vanno controllate e corrette dalla scheda utente. Dove si scrive ancora il nome intero (certificati, notifiche) resta «Nome Cognome»",
    ]},
    {"version": "2.2.0", "date": "2026-10", "label": "Permessi, uffici e mansioni", "changes": [
        "Il ruolo unico dell'utente è sostituito da permessi che si sommano (Admin, Formazione) e dalla qualifica Docente; senza nessuno dei tre si è utenti semplici. Si assegnano dalla scheda di ciascun utente (nuovo pulsante Modifica nell'elenco)",
        "Gli uffici sono la sola struttura organizzativa: albero di uffici e sottouffici con responsabile, un solo ufficio per persona (obbligatorio per gli interni, tranne gli Admin). I quattro gruppi di sistema, che non facevano nulla, e la pagina Ruoli sono stati tolti",
        "Nuove mansioni: etichette trasversali agli uffici (per esempio preposto, addetto antincendio), anche più d'una per persona, senza permessi; servono ad assegnare un percorso in blocco e a filtrare l'elenco utenti",
        "Come docente di un'edizione si possono scegliere solo i Docenti e gli utenti esterni (un esterno è un docente di una società terza: non ha ufficio né mansioni e non si iscrive ai corsi)",
        "L'importazione CSV usa le colonne ufficio, mansioni, admin, formazione, formatore al posto di role e gruppi (dalla 2.3.4 la colonna si chiama docente); la configurazione esportata include le mansioni e i file vecchi si importano ancora",
        "Chi aggiorna: la migrazione trasforma i dati esistenti (ruoli in permessi, gruppi liberi che non erano uffici in mansioni, chi era docente o nel vecchio gruppo «Formatori» diventa Docente); chi era in più uffici resta nel primo e la migrazione lo scrive nel log. Il profilo si rilegge dal server a ogni avvio, quindi il menu si aggiorna senza rifare l'accesso",
    ]},
    {"version": "2.1.0", "date": "2026-10", "label": "Pagina Utenti a schede", "changes": [
        "La pagina Utenti è divisa in tre schede: Elenco, Nuovo utente, Importa da CSV, così non diventa lunghissima con molti utenti",
        "L'elenco ha ricerca per nome o email, filtri per ruolo, gruppo, tipo e stato, intestazioni cliccabili per ordinare (senza badare alle maiuscole, con i numeri trattati come numeri), paginazione a 25, 50 o 100 righe e mostra anche i gruppi di ciascuno",
        "Dalla pagina Gruppi è stato tolto il pulsante Esporta (l'esportazione della configurazione resta nella pagina Configurazione)",
    ]},
    {"version": "2.0.0", "date": "2026-10", "label": "Pronta per l'uso aziendale", "changes": [
        "Chiude la serie di sicurezza 1.9: video non pubblici con indirizzi a tempo, file e video cifrati su disco, dati personali cifrati nel database, registro attività con conservazione limitata ed esportazione, librerie senza vulnerabilità note, immagini Docker senza problemi alti o critici",
        "Controlli automatici su GitHub Actions a ogni pull request e a ogni push su master (test, analisi del codice con Bandit, librerie Python e del sito, immagini Docker con Trivy); gli stessi controlli di sicurezza si lanciano a mano con scripts/controlli-sicurezza.sh, la suite di test con docker compose --profile test run --rm tests; revisione automatica del codice con CodeRabbit sulle pull request",
        "docs/sicurezza.md descrive cosa è protetto, cosa no e cosa resta a carico di chi installa (HTTPS, cifratura del disco, backup, custodia della chiave)",
        "Corretto l'elenco delle librerie nella pagina Informazioni: mostrava ancora la libreria sostituita nella 1.9.5",
    ]},
    {"version": "1.9.7", "date": "2026-10", "label": "Dati personali cifrati nel database", "changes": [
        "Nome ed email degli utenti, referente/email/telefono degli enti esterni, email, IP e dettaglio del registro attività sono cifrati nella colonna (AES-256-GCM, stessa chiave dei file): chi legge il database vede solo testo cifrato",
        "Per l'accesso e i controlli di unicità l'email ha un'impronta (HMAC con una chiave propria): l'email è la stessa senza badare alle maiuscole e due account non possono avere lo stesso indirizzo. Il registro filtra per email o IP interi; ordinamento e ricerca per nome si fanno nel programma",
        "Per gli eventi sugli utenti il nome dell'entità (l'email) passa nel dettaglio cifrato; gli accessi falliti registrano l'indirizzo digitato, così si cercano per email",
        "I dati esistenti si convertono con python -m app.cifratura_cli cifra (a lotti); la pagina Stato mostra quanti valori sono ancora in chiaro (per il registro attività conta solo le ultime 10000 righe: il comando `stato` da riga di comando le conta tutte); ruota e decifra valgono anche per questi dati. Un confronto scritto per errore su una colonna cifrata dà un errore invece di non trovare nulla in silenzio",
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
        "Test: il docente gestisce il test solo con una sessione pianificata o in corso. Importazione configurazione: un ufficio nullo nel file non cancella quello esistente. Offboarding: i posti liberati non contano chi era in lista d'attesa",
    ]},
    {"version": "1.8.3", "date": "2026-10", "label": "Correzioni dalla quarta revisione del codice", "changes": [
        "Utenti: non si può più cambiare il ruolo di sé stessi né dell'ultimo Admin tecnico attivo (la piattaforma non resta senza amministratori)",
        "Auto-iscrizione: possibile solo in sessioni pianificate o in corso, anche all'approvazione del responsabile",
        "Password dimenticata e inviti da import CSV: le email partono in sottofondo e solo a salvataggio riuscito (nessuna differenza di tempi tra account esistenti e no, nessun link morto)",
        "Esportazioni CSV/Excel: i testi che iniziano con = + - @ vengono neutralizzati (niente formule iniettate da nomi o commenti)",
        "Test: il docente gestisce il test solo finché ha una sessione del corso ancora aperta e può vedere le risposte corrette",
        "Sincronizzazione Entra: il freno di sicurezza non permette di disattivare più della metà degli utenti in ambito (minimo 2), anche su installazioni piccole",
        "Importazione configurazione: i gruppi di sistema non si toccano e i campi assenti nel file non cancellano quelli esistenti",
        "Accesso: un login sbagliato mostra il messaggio d'errore invece di ricaricare la pagina",
    ]},
    {"version": "1.8.2", "date": "2026-10", "label": "Correzioni dalla terza revisione del codice", "changes": [
        "Gruppi e uffici: non si può più creare un giro nella gerarchia (un ufficio sotto un suo sotto-ufficio), e le visite della gerarchia non si bloccano nemmeno con dati incoerenti",
        "Iscrizioni: oltre la capienza le persone in più vengono segnalate invece di far fallire tutta l'iscrizione, e non si supera mai il numero di posti; niente iscrizioni in sessioni chiuse o annullate (né in bozza per i responsabili); più posti o lista d'attesa attivata fanno salire subito chi aspetta, che riceve l'invito calendario anche dopo la disattivazione di un collega",
        "Sessioni: pianificare due volte non rimanda gli inviti e una sessione chiusa non torna pianificata",
        "Test: il docente che modifica un test vede e conserva le risposte corrette; salvare un test con risposte non dà più errore",
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
    if not user.is_admin:
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
