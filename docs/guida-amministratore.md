# Guida dell'amministratore

Per chi configura e fa funzionare la piattaforma (permesso **Admin**) e per chi ha il permesso **Formazione**. Le voci di menu sono scritte come nell'app.

## 1. Prima configurazione (nell'ordine)
1. **Primo avvio**: crea l'Admin tecnico. Conserva bene la password: è anche l'accesso di emergenza se l'accesso aziendale non funziona.
2. **Impostazioni → Azienda**: ragione sociale, partita IVA, indirizzo, PEC, logo. Compaiono su attestati ed export.
3. **Impostazioni → Piattaforma**: nome, **URL pubblico** (indispensabile per i link nelle email) e icona dell'app.
4. **Impostazioni → Informativa privacy**: testo e/o PDF; ogni utente la legge da *Impostazioni utente → Privacy*. Nessuna accettazione al login.
5. **Uffici**: crea la struttura (uffici e sottouffici). Ogni ufficio ha un **responsabile**; la gerarchia dei sottouffici determina chi approva e chi vede le richieste. **Mansioni**: crea le categorie trasversali (per esempio preposto, addetto antincendio) per assegnare percorsi in blocco.
6. **Etichette dei corsi**: il sistema non ne propone di già pronte, le definisci tu. Crea le *famiglie* che ti servono (per esempio tematica, riferimento normativo, ambito, obbligo), aggiungi le loro etichette e decidi quali famiglie sono obbligatorie per ogni corso. Poi assegna le etichette ai corsi dalla pagina Corsi (che ha anche il collegamento alla gestione delle etichette).
7. **Utenti**: crea o importa le persone (vedi sotto).
8. **Corsi**, **Template attestati**, **Percorsi formativi**, **Sessioni**.
9. **Impostazioni → Stato piattaforma**: verifica posta, accesso aziendale, spazio e job notturni.

## 2. Utenti
- La pagina ha tre schede: **Elenco** (cerca per nome, cognome o email, filtra per ruoli, ufficio, mansione e stato, clicca sulle intestazioni per ordinare, scegli quante righe per pagina), **Nuovo utente** e **Importa da Excel o CSV**.
- **Chi è chi**: un utente è **interno** (persona dell'organizzazione, oggetto di formazione) o **esterno** (docente di una società terza: ha un'organizzazione, non ha ufficio né mansioni, non si iscrive ai corsi). Ogni interno sta in **un solo ufficio** (obbligatorio, tranne per chi è Admin). Nell'elenco i ruoli sono **capsule colorate** (rosso Admin, blu Formazione, verde Docente, viola Esterno, grigio Utente), con una legenda sopra la tabella. Dalla scheda di ciascun utente (*Modifica*) si assegnano i permessi, che si sommano: **Admin** (configura la piattaforma, ha anche i poteri della Formazione), **Formazione** (corsi, edizioni, iscrizioni, attestati), e la qualifica **Docente** (può essere scelto come docente nelle edizioni, senza poteri in più). Senza nessuna spunta è un utente semplice. Le **mansioni** sono etichette trasversali agli uffici, anche più d'una per persona, senza permessi.
- **Uffici**: *Modifica* permette di cambiare nome, descrizione, colore, responsabile, stato e posizione nella gerarchia («Sottoufficio di», oppure «nessuno» per portarlo al primo livello). Negli elenchi gli uffici sono in ordine alfabetico e scritti con il percorso intero (`Produzione / Linea 2`).
- **Nome e cognome** sono due campi separati: si mostrano entrambi nell'elenco e si può cercare e ordinare per ciascuno. Le persone esistenti prima della 2.3.0 sono state divise così: la prima parola è il nome, il resto il cognome (per «Maria Grazia Rossi» o «Mario De Luca» non c'è una regola esatta): controllale e correggile da *Modifica*. Con l'accesso aziendale e la sincronizzazione da Entra si usano nome e cognome dell'azienda, quando ci sono.
- **Nuovo utente**: la password iniziale è facoltativa. Con posta e URL pubblico attivi la persona riceve un link (valido 3 giorni) per scegliere la propria password; altrimenti vedi una password temporanea, **una volta sola**, da comunicare a parte. Al primo accesso con una password assegnata si deve sceglierne una propria.
- **Importazione da Excel o CSV** (scheda *Importa da Excel o CSV*): scarica un **modello** (Excel o CSV, per nuovi utenti o per i cessati): ha le colonne giuste, una riga di esempio da cancellare e, nel modello Excel, i fogli *Uffici* e *Mansioni* con i nomi validi (la colonna Ufficio ha un menu a tendina). Colonne: `email`, `nome`, `cognome`, `ufficio`, facoltative `password`, `admin`, `formazione`, `docente` (sì/no), `mansioni` (separate da `;`), `is_external`, `organizzazione`, `data_ingresso`. Il file può essere `.xlsx` o CSV. L'ufficio si scrive con il nome o, se il nome si ripete, con il percorso intero (`Produzione / Linea 2`).
  - **Prima si controlla, poi si importa**: caricando il file si apre una finestra con il riepilogo per persona. Solo con *Importa comunque* si crea qualcosa; con *Annulla* non è successo niente (e non parte nessuna email).
  - **Uffici e mansioni non vengono mai creati dal file.** Se un ufficio o una mansione non esiste, oppure l'ufficio è vuoto, la persona viene creata *senza* e il riepilogo lo scrive (per esempio «Mario Rossi: ufficio *Produzione 2* non presente»). Si possono ritrovare con il filtro *Senza ufficio* nell'elenco e sistemare da *Modifica*. Le righe inutilizzabili (email, nome o cognome mancanti, email già presente, esterno senza organizzazione, password o data non valide) vengono scartate; le altre proseguono.
  - Dopo l'importazione si scarica il **riepilogo dei problemi**. Un vecchio file `.xls` non si carica: salvalo come `.xlsx` o CSV. Per **disattivare** i cessati scegli «Disattiva cessati» (basta la colonna `email`; gli Admin non si disattivano da qui).
- **Disattivare un utente** chiude l'account e le sessioni, annulla le iscrizioni aperte (chi era in lista d'attesa sale) e toglie dispositivi e calendario. Lo storico formativo resta. Docenze aperte e responsabilità di ufficio vengono segnalate da riassegnare.
- **Reset password**: se la posta non è attiva le richieste arrivano nella voce *Reset password*; generi una password temporanea da comunicare a parte.
- **Accessi**: password di almeno 14 caratteri, con una maiuscola, un numero e un carattere speciale; dopo 5 tentativi falliti l'account è sospeso 15 minuti (la risposta è identica a una password sbagliata) e gli Admin tecnici ricevono una notifica; *Password dimenticata* toglie la sospensione.

## 3. Accesso aziendale e sincronizzazione (facoltativi, da `.env`)
- **Accesso aziendale (SSO)**: configurato in `.env`. Un utente esistente si collega al primo accesso per email; l'Admin tecnico non si collega e resta con la password. Con `SSO_PROVISIONA_UTENTI=true` chi non esiste viene creato come utente semplice.
- **Sincronizzazione utenti da Entra ID** (*Sincronizzazione utenti*): il gruppo Entra indicato definisce chi usa la piattaforma. **Guarda sempre l'anteprima** prima di applicare: mostra chi viene creato, aggiornato, disattivato. Mai toccati: utenti esterni, Admin tecnici, altri domini. Con `ENTRA_SYNC_AUTO=true` il giro è notturno, con un freno se le disattivazioni sono troppe.

## 4. Corsi e formazione
- **Corso**: titolo, validità in mesi (vuoto = nessuna scadenza), test finale, auto-iscrizione, **etichette**. Le etichette si scelgono da un elenco; quelle obbligatorie impediscono di salvare un corso incompleto.
- **Rinnovo automatico** (solo con una validità): iscrive la persona alla prossima sessione utile prima della scadenza (giorni di anticipo a tua scelta). Se non ci sono sessioni disponibili ricevi un avviso. «Chi verrebbe iscritto» mostra l'anteprima.
- **Nuova versione** di un corso: scegli se chi lo ha già fatto deve ripeterlo (aggiornamenti normativi) o solo vedere «aggiornamento disponibile».
- **Percorsi formativi**: sequenze di corsi con propedeuticità, assegnabili a mano, all'ingresso in azienda, a un ufficio (sottouffici compresi) o a una mansione.
- **Sessioni**: modalità presenza, ibrida, remoto, video, esterna. Una sessione video senza data resta sempre aperta (adatta al rinnovo automatico). Pianificare una bozza manda l'invito calendario agli iscritti.
- **Video**: carica il file, la piattaforma lo converte; puoi aggiungere capitoli e sottotitoli (`.vtt`).

## 5. Controllo e audit

- **Audit log** (solo Admin tecnico): di default mostra gli eventi importanti; scegli «Tutti» per vedere anche accessi riusciti e attività di routine. In cima trovi i contatori delle ultime 24 ore, 7 e 30 giorni. Gli eventi si conservano per `AUDIT_RETENZIONE_MESI` mesi (24 di default) e poi vengono cancellati ogni notte; per archiviarli o inviarli a un sistema di gestione dei log, vedi `AUDIT_EXPORT_DIR` e `AUDIT_LOG_STDOUT` nel README.
- **Registro formazione**, **Matrice formativa** (persone × corsi richiesti dai percorsi, con stato di ogni cella) e **Dashboard** si filtrano per ufficio, persona, periodo ed **etichetta**.
- **Pacchetto ispezione** (dal Registro): uno ZIP con registro, matrice, attestati emessi e caricati e un indice, per l'intera azienda o per un perimetro (ufficio, persona, etichetta, periodo). Per un audit su una norma filtra per *Riferimento normativo*.
- **Audit log** (*Impostazioni*): chi ha fatto cosa, quando e da dove, con filtri ed export. Le azioni dei discenti (check-in, test, video) sono registrate; il gradimento resta anonimo.

## 6. Fabbisogno formativo
- **Campagna**: la avvii dalla scheda *Nuova campagna*. Ogni responsabile di un ufficio di primo livello può rispondere (più esigenze per invio) o **girare** l'invito ai sotto-uffici. Le risposte dei sotto-uffici salgono ai responsabili sopra, che le **approvano, rifiutano o uniscono** se simili; l'unione conserva sempre la provenienza.
- **Richieste formative** (scheda): vista per argomento o elenco, con filtri, ordinamento ed export.
- Un responsabile può anche aprire una **richiesta spontanea** in qualsiasi momento.

## 7. Configurazione portabile
*Impostazioni → Configurazione*: **esporta** dati aziendali, uffici, mansioni, società di formazione, corsi, percorsi ed etichette in un file; **importa** su un altro ambiente con anteprima. Non cancella nulla. Restano fuori persone, iscrizioni, video, immagini, template degli attestati, test e credenziali.

## 8. Quando qualcosa non va
- *Stato piattaforma*: posta, accesso aziendale, job notturni (con errore), spazio, video in errore.
- Le email non partono: controlla `SMTP_*` e che l'URL pubblico sia impostato.
- Un utente non entra: guarda l'*Audit log* (tentativi, sospensione) e, se serve, genera una password temporanea.
- Dopo un aggiornamento: le migrazioni sono automatiche; nei log del backend compare «schema aggiornato».
