# Progetto: persone, permessi, uffici e mansioni

Nota: nel progetto la qualifica si chiamava «Formatore»; dalla 2.3.4 nell'app e nei documenti è **«Docente»** (nel codice resta `is_formatore`, perché `is_docente` è già «ha un'edizione assegnata»).

Documento di progetto per la release 2.2.0, scritto prima di sviluppare per decidere sulla carta cosa cambia. La release è stata poi realizzata come descritto (con la variante che l'elenco di chi ha una mansione si ottiene filtrando in Utenti); il documento resta come motivazione delle scelte.

## 1. Il modello in una pagina

Un **utente** è una persona. È **interno** (della organizzazione che usa la piattaforma) oppure **esterno** (docente incaricato da una società terza).

| Concetto | Che cos'è | Dove si imposta |
|---|---|---|
| **Admin** | permesso (sì/no): configura la piattaforma | scheda utente |
| **Formazione** | permesso (sì/no): gestisce corsi, edizioni, iscrizioni, attestati | scheda utente |
| **Docente** | qualifica (sì/no): può essere scelto come docente | scheda utente |
| **Ufficio** (gruppo) | struttura ad albero, con un responsabile; **uno solo per persona** | scheda utente / pagina Gruppi |
| **Mansione** | etichetta trasversale, anche più d'una per persona, senza gerarchia né responsabile | scheda utente / pagina Mansioni |

Regole:
- **Esterno**: non è oggetto di formazione, è docente per definizione (Docente implicito), appartiene a una società terza (organizzazione), non ha ufficio né mansioni, non entra con l'accesso aziendale (come oggi).
- **Interno**: oggetto di formazione. Può avere qualsiasi combinazione di Admin, Formazione, Docente. Senza nessuno dei tre è un utente semplice.
- **Ufficio**: obbligatorio per ogni interno, tranne chi ha il permesso Admin (il primo Admin, creato alla configurazione iniziale, non ne ha uno).
- **Responsabile** di un ufficio: un utente interno. La gerarchia dei responsabili si deriva dall'albero degli uffici, come oggi.
- Chi ha **Formazione** è comunque una persona da formare: riceve iscrizioni, scadenze e attestati come gli altri.

## 2. Com'è oggi (verificato sul codice)

- Ogni utente ha **un solo ruolo**: `admin_tecnico`, `training_admin` o `user`. Il codice lo controlla in circa 36 punti del backend e 8 del sito.
- L'Admin tecnico può già fare **tutto** quello che fa l'Ufficio formazione (i controlli sono sempre «admin o formazione»), più la configurazione.
- Alla configurazione iniziale si creano 4 **gruppi di sistema**: Admin, Ufficio Formazione, Formatori, Utenti. **Nessuna parte del programma li usa** per decidere permessi o chi può fare il docente.
- Nelle edizioni il docente si sceglie tra **tutti** gli utenti attivi.
- I gruppi liberi hanno un segno «È un ufficio». Gli uffici hanno responsabile e albero. Una persona può stare in più gruppi (e in più uffici: la gerarchia lo gestisce, per esempio per il part-time).
- I percorsi si assegnano automaticamente per «ingresso in azienda» oppure per **gruppo** (compresi i sottogruppi).

## 3. Cosa cambia

### 3.1 Utenti
- Il ruolo unico diventa tre interruttori: `is_admin`, `is_formazione`, `is_formatore` (nell'app la qualifica si chiama «Docente»).
- Nel codice i controlli diventano due funzioni sole («ha poteri di formazione», «è admin»), così non ci sono più 36 confronti sparsi.
- Il permesso **Admin** continua a includere i poteri della Formazione (come oggi, per non rompere nulla). Il tag Formazione indica *chi fa parte* dell'ufficio formazione: compare negli elenchi e riceve gli avvisi dedicati.
- Gli avvisi che oggi vanno a «Admin tecnici e Ufficio formazione» continuano ad andare a entrambi.
- Il campo `can_see_all` (visibilità totale) non cambia.

### 3.2 Docenti
- Essere docente di un'edizione resta una proprietà **dell'edizione** (tabella dei docenti dell'edizione), non della persona: i poteri sull'edizione (presenze, validazione, comunicazioni) restano di chi vi è assegnato. La qualifica Docente decide solo **chi si può assegnare**: oggi l'assegnazione non controlla nulla e accetta chiunque.
- Nelle edizioni si potranno scegliere solo persone con **Docente** (interne) e gli **esterni**.
- Chi è già docente di un'edizione esistente riceve la qualifica Docente, così nessuna edizione passata perde il suo docente.
- Gli altri elenchi di persone (scelta del responsabile, registro formazione) continuano a mostrare tutti.

### 3.3 Gruppi = uffici
- I gruppi diventano **solo uffici**: albero, responsabile, uno per persona.
- Spariscono i 4 gruppi di sistema.
- La scheda utente ha un solo campo «Ufficio». Alla creazione e alla modifica.

### 3.4 Mansioni (nuove)
- Una mansione ha nome, descrizione, colore, attiva sì/no. Nessuna gerarchia, nessun responsabile.
- Una persona può averne quante vuole. Si assegnano dalla scheda utente e dalla pagina Mansioni (con il numero di persone; l'elenco si ottiene filtrando in Utenti).
- Servono a due cose: **assegnare percorsi in blocco** (nuovo tipo di assegnazione «mansione») e **filtrare** gli elenchi (pagina Utenti, matrice di ispezione).
- Non danno permessi.

## 4. Chi può fare cosa

| Azione | Utente semplice | Docente | Formazione | Admin |
|---|---|---|---|---|
| Vedere i propri corsi, iscrizioni, attestati | sì | sì | sì | sì |
| Essere scelto come docente | no | sì | solo se Docente | solo se Docente |
| Gestire le proprie edizioni da docente (presenze, validazione) | no | sì | sì | sì |
| Corsi, percorsi, edizioni, iscrizioni, attestati, fabbisogno, richieste | no | no | sì | sì |
| Vedere i sottoposti e approvare (responsabile di ufficio) | se responsabile | se responsabile | se responsabile | se responsabile |
| Utenti, uffici, mansioni | no | no | no | sì |
| Configurazione, accesso aziendale, sincronizzazioni, stato, registro attività | no | no | no | sì |

(La colonna «Formazione» e «Admin» ripete come oggi la regola «admin o formazione» per le prime righe.)

## 5. Trasformazione dei dati esistenti (migrazione)

| Oggi | Diventa |
|---|---|
| ruolo `admin_tecnico` | `is_admin` |
| ruolo `training_admin` | `is_formazione` |
| membro del gruppo di sistema «Formatori» **o** docente di almeno un'edizione | `is_formatore` (in app «Docente») |
| gruppi di sistema (Admin, Ufficio Formazione, Formatori, Utenti) | eliminati, con le loro iscrizioni |
| gruppo libero con «È un ufficio» | resta ufficio |
| gruppo libero senza «È un ufficio» | diventa mansione; i membri ricevono la mansione |
| percorso con assegnazione per gruppo-non-ufficio | assegnazione per la mansione corrispondente |
| persona in più uffici | resta nel primo; gli altri vengono elencati nel messaggio della migrazione (log di avvio) per essere sistemati a mano |

La migrazione è idempotente come le altre, e si rifiuta di tornare indietro se perderebbe dati.

## 6. Casi limite e decisioni prese

- **Persona senza ufficio**: ammessa solo se Admin (il primo Admin). Per gli altri interni l'ufficio è obbligatorio alla creazione; l'importazione CSV lo segnala come errore di riga.
- **Ultimo Admin**: non si può togliere il permesso né disattivare l'ultimo Admin attivo (come oggi). Nessuno toglie l'Admin a sé stesso.
- **Solo un Admin assegna i permessi** Admin, Formazione e Docente.
- **Responsabile che cambia ufficio o viene disattivato**: come oggi, la disattivazione segnala gli uffici da riassegnare.
- **Docente esterno**: Docente implicito; non si può rendere «interno» senza ufficio.
- **Ufficio senza responsabile**: ammesso (come oggi); la gerarchia sale al padre.
- **Gruppo con sottogruppi che diventa mansione**: le mansioni sono piatte; i sottogruppi non-ufficio diventano mansioni a sé e un percorso assegnato al gruppo padre non raggiungerà più chi stava solo nei figli (caso raro, segnalato nel risultato della migrazione).
- **Accesso aziendale ed Entra**: le persone create automaticamente sono utenti semplici interni, senza ufficio, e compaiono in un elenco «da collocare» per l'Admin.
- **Importazione CSV**: colonne `ufficio` (nome del percorso intero, es. `Produzione / Linea 2`) e `mansioni` (nomi separati da `;`); al posto di `role` le colonne `admin`, `formazione`, `docente` (sì/no).

## 7. Cosa NON cambia
Esterni e organizzazioni, assegnazione per ingresso in azienda, fabbisogno formativo, gerarchia dei responsabili, SSO, cifratura, registro attività.

## 8. Piano
1. Migrazione e modello (utenti con tre interruttori; mansioni; eliminazione dei gruppi di sistema).
2. Backend: funzioni di permesso uniche, filtro docenti, mansioni (API, assegnazione dei percorsi), un solo ufficio per persona, CSV, SSO ed Entra.
3. Sito: scheda utente (modifica con permessi, ufficio, mansioni), pagina Mansioni, pagina Gruppi (solo uffici), filtri nell'elenco utenti, scelta docenti.
4. Test (compresa la migrazione su una copia di dati realistici), documenti, changelog, ROADMAP.

Release: **2.2.0**. Nome e Cognome nella **2.3.0**, nella stessa PR.
