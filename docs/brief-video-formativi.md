# Brief per creare un videocorso (da incollare in una chat nuova)

Come si usa: apri una chat nuova con Claude, incolla tutto da «Contesto» in giù dopo aver compilato i campi `[...]`, e rispondi alle domande che ti fa. Il risultato è un pacchetto pronto da portare in Clipchamp (video) e nella piattaforma (sottotitoli, capitoli, quiz).

---

## Contesto

Devi aiutarmi a produrre un **videocorso interno** per i dipendenti della nostra azienda. Il video verrà montato in Microsoft Clipchamp con Copilot (voce sintetica italiana, filmati d'archivio, testi in sovraimpressione) e caricato sulla nostra piattaforma e-learning, che offre: player con capitoli, sottotitoli `.vtt`, blocco del salto in avanti, e test a risposta multipla con soglia di superamento.

Non puoi generare video né audio: scrivi i testi e le indicazioni, io faccio il montaggio.

**Dati del corso (compilali tu):**
- Argomento: `[es. Protezione dei dati personali per chi lavora in ufficio]`
- Pubblico: `[chi lo vedrà, che cosa sa già]`
- Durata obiettivo: `[es. 6-8 minuti]` — parti sempre da qui, non allungare.
- Tono: `[es. diretto, concreto, dai del "tu"; niente burocratese]`
- Lessico e regole interne da rispettare: `[nomi di procedure, strumenti, uffici]`
- Riferimenti normativi che conosco e posso fornire: `[articoli, policy; se non ne indico, non inventarne]`
- Obiettivo: cosa deve saper fare la persona alla fine: `[2-3 comportamenti concreti]`

## Cosa voglio in uscita (in quest'ordine, un blocco alla volta)

1. **Scaletta** a scene, con titolo e durata stimata di ciascuna, e chi/che cosa si vede. Aspetta il mio ok prima di scrivere il testo.
2. **Copione** diviso in scene. Per ogni scena due colonne chiare: **Voce narrante** (testo da far leggere alla voce sintetica, frasi brevi, numeri e sigle scritti come si pronunciano, niente parentesi) e **Immagini e testi a schermo** (che filmato d'archivio cercare, quale scritta mostrare). Circa 130-150 parole al minuto di narrazione.
3. **Capitoli** nel formato `titolo | inizio in secondi`, coerenti con le durate delle scene.
4. **Sottotitoli** in formato WebVTT (`WEBVTT`, poi blocchi con tempi `00:00:00.000 --> 00:00:04.000`), costruiti dal copione con i tempi calcolati sulla durata di lettura. Dopo il montaggio ti darò la durata reale per riallinearli.
5. **Quiz finale**: 6-8 domande a risposta multipla (4 opzioni, una sola corretta), che verificano i comportamenti dell'obiettivo e non la memoria di dettagli. Per ogni domanda indica la risposta corretta e perché le altre sono sbagliate. Formato:
   `Domanda | A) ... | B) ... | C) ... | D) ... | Corretta: B`
6. **Istruzioni per Clipchamp**: il prompt da dare a Copilot e dove inserirlo (la pagina iniziale di Clipchamp, il comando «Genera un video» nell'editor o l'area *Create* di Copilot: dipende dall'account e dalla versione, e la funzione richiede un account di lavoro con Copilot e Clipchamp abilitato dall'amministratore, quindi controlla quale voce vedi), e come sostituire la bozza con il tuo copione se la voce o le immagini non vanno bene.

## Regole

- Scrivi in italiano corrente, senza gergo non spiegato.
- **Non inventare** norme, articoli, sanzioni, numeri o procedure. Se un dato serve e non me lo hai dato, mettilo in una lista «Da verificare» a fine documento invece di scriverlo nel copione.
- Una sola idea per scena; ripeti i punti chiave una volta, non di più.
- Niente nomi di persone reali né dati personali negli esempi.
- Segnala se il tema, per la sua natura (sicurezza sul lavoro, obblighi di legge), richiede che il contenuto sia validato da un responsabile prima della pubblicazione.

## Prima di cominciare

Fammi le domande che ti servono per i campi mancanti, poi proponi la scaletta (punto 1).

---

## Dopo la chat: portare tutto in piattaforma

1. **Video**: in Clipchamp esporta in MP4 (1080p va bene). Nella piattaforma: *Video* → carica il file e attendi che lo stato diventi «pronto» (viene convertito in automatico).
2. **Sottotitoli**: aggiorna i tempi del `.vtt` con la durata reale, poi carica il file dalla scheda del video.
3. **Capitoli**: aggiungili dalla scheda del video (titolo e secondo di inizio).
4. **Quiz**: *Corsi* → «Gestisci test» → crea il test finale e inserisci le domande; imposta la soglia di superamento.
5. **Sessione**: crea una sessione in modalità *video* collegata al contenuto. Se il corso ha una validità e vuoi il rinnovo automatico, spunta l'opzione nelle impostazioni del corso: una sessione video sempre aperta funziona bene.
6. **Prima di pubblicarlo**: guardalo tu dall'inizio alla fine con la voce sintetica italiana scelta, controlla pronuncia di sigle e nomi, e fallo vedere a una persona del pubblico.
