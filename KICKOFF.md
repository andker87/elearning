# Kickoff — Piattaforma E-Learning aziendale

Questo documento è un **briefing di contesto e di processo** per iniziare questo progetto con Claude, non una specifica di prodotto. Le specifiche vere (contenuti, struttura corsi, utenti target, requisiti tecnici) te le darà Andrea direttamente in questa conversazione — leggi questo documento e poi chiediglieli, non inventarli.

## Contesto

Andrea sta sviluppando internamente una piattaforma GRC/Compliance (GDPR/ISO27001) in un progetto separato (`/home/andrea/server/compliance`), con un'ambizione commerciale dichiarata di poterla offrire un giorno anche ad altre aziende (modello non ancora deciso: gratis, a pagamento, ecc.).

Questo progetto di e-learning nasce con lo stesso spirito e la stessa motivazione di fondo: la sua azienda oggi non ha una piattaforma di formazione — gestisce tutto con video salvati in cartelle di rete e registri cartacei — e le piattaforme LMS commerciali sono troppo costose per il budget che il board è disposto ad approvare. L'idea è costruirsela, con la possibilità (non l'obbligo) di diffonderla più avanti come ha in mente di fare per il GRC.

## Domanda architetturale aperta (non risolta, non bloccante)

Andrea si è chiesto se ha senso unire GRC + e-learning in un'unica mega-piattaforma modulare. La conclusione discussa con lui nella sessione del progetto GRC (2026-09-11): **non un monolite unico, non due mondi isolati**. Motivazioni:

- Popolazioni utenti molto diverse: il GRC lo usano pochi ruoli specialistici con permessi fini; l'e-learning lo usa potenzialmente tutta l'azienda (autenticazione di massa, video, progress tracking, forse anche esterni/collaboratori).
- L'e-learning ha esigenze di storage/banda (contenuti video) che il GRC oggi non ha — mischiare i deploy rischia di far pagare all'uno i problemi di scala dell'altro.
- Il GRC è già in produzione: modifiche strutturali condivise rischiano di destabilizzarlo per un guadagno oggi solo ipotetico.
- Tenerle disaccoppiate lascia ad Andrea libertà commerciale futura (vendere/offrire l'una senza l'altra).

**Indicazione per questo progetto**: procedi come applicazione separata (repository proprio, deploy proprio), MA tieni a mente — senza bloccarti su questo ora — che in futuro le due piattaforme potrebbero condividere un nucleo comune (utenti, gruppi/permessi, dati azienda, notifiche, audit log) via un livello di identità condiviso (tipo SSO), non un database unico. Non serve progettare oggi quella integrazione: basta non scegliere modelli dati così idiosincratici da rendere quell'opzione impossibile domani (es. un concetto di "utente" e "ruolo" ragionevolmente allineato a quello che si userebbe in qualunque altro contesto aziendale, non qualcosa di esotico solo per comodità a breve termine).

Se in una fase avanzata del progetto emerge un'esigenza concreta di integrazione con il GRC, chiedi ad Andrea prima di assumere qualunque soluzione — è una decisione sua, non tecnica.

## Come Andrea preferisce lavorare (osservato nel progetto GRC)

Queste sono convenzioni di collaborazione emerse lavorando con lui sul progetto GRC — non tutte si applicheranno necessariamente 1:1 qui, ma partono da un track record reale:

- **Discussione aperta prima del codice, sulle decisioni non banali.** Per il workflow approvativo del Data Breach, Andrea ha esplicitamente rifiutato un menu di opzioni multiple e ha preferito ragionare "a voce alta" sezione per sezione fino a convergere insieme su un disegno. Quando una decisione ha più sfaccettature reali (non solo "A o B"), proponi un ragionamento e una raccomandazione, non un questionario a scelta multipla imposto dall'alto.
- **Verifica reale prima di costruire sopra.** Per ogni funzionalità backend, crea dati/utenti di test veri (via script diretti, non mock), chiama le API vere, verifica il comportamento con asserzioni concrete, e SOLO DOPO costruisce l'interfaccia sopra. Pulisce sempre i dati di test a fine verifica — l'ambiente di sviluppo/produzione è condiviso con l'uso reale che Andrea ne fa in parallelo, quindi mai lasciare residui (utenti fittizi, record di prova) in giro.
- **Verifica visiva reale per le modifiche UI**, non solo "il build passa" — screenshot di un vero browser (headless), guardati davvero, prima di dichiarare fatto un cambiamento visivo.
- **Deploy**: dopo ogni modifica al codice, ricostruire e riavviare i container (`docker compose up -d --build <servizio>`), mai solo build.
- **Git**: commit solo quando esplicitamente richiesto, mai in autonomia.
- **Versioning**: assegna un numero di versione solo quando un tema diventa "il prossimo su cui si lavora" — mai pre-assegnare numeri a temi lontani nella roadmap (causa disallineamenti).
- **Niente scope creep**: una richiesta specifica va risolta in modo specifico, senza refactoring o "miglioramenti" non richiesti aggiunti di striscio.
- **Feedback concreto e iterativo**: aspettati più giri di correzione fine (es. dimensioni di un badge, allineamento di una colonna) prima che qualcosa sia "giusto" — non è indecisione, è cura del dettaglio. Chiedigli sempre conferma visiva/funzionale dopo un cambiamento percepibile, non darla per scontata.
- **È un interlocutore tecnico competente** (gestisce lui stesso l'infrastruttura server, Docker, ecc.) — non serve semplificare eccessivamente le spiegazioni tecniche, ma apprezza capire il "perché" dietro un compromesso o una scelta architetturale, non solo il "cosa".

## Cosa NON troverai in questo documento

Deliberatamente non ci sono: struttura dei corsi, tipi di contenuto, requisiti di quiz/certificazioni, scelte di hosting/storage per i video, target (solo dipendenti o anche esterni), stack tecnologico. Sono tutte cose che Andrea ti spiegherà lui stesso — il tuo primo compito in questa conversazione è ascoltare quel contesto, non proporre un'architettura a scatola chiusa.

## Suggerimento per il primo scambio

Non partire proponendo un'architettura. Parti chiedendo ad Andrea di descrivere il processo attuale (i video in cartella, i registri cartacei) e cosa vorrebbe che succedesse invece — esattamente come è stato fatto per il workflow Data Breach nel progetto GRC, dove il disegno finale è emerso da un dialogo reale sul processo esistente, non da una lista di feature calate dall'alto.
