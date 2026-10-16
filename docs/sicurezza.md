# Sicurezza dei dati

Questo documento descrive come la piattaforma protegge i dati e **che cosa resta a carico di chi la installa**. Vale per qualsiasi azienda che la usi.

## 1. Che cosa è protetto e come

| Cosa | Dove | Protezione |
|---|---|---|
| Password degli utenti | database | hash bcrypt (non recuperabili) |
| Token di reimpostazione password | database | solo impronta (hash) |
| Link del calendario | database | solo impronta SHA-256; il link si vede una volta sola, alla creazione |
| Chiave privata delle notifiche push (VAPID) | database | cifrata con `CHIAVE_CIFRATURA` |
| Attestati emessi, attestati esterni caricati, template, informativa, logo, icona | volume `uploads` | **cifrati su disco** (AES-256-GCM) con `CHIAVE_CIFRATURA` |
| Video e sottotitoli | volume `videos` | non pubblici: indirizzi a tempo legati a chi ha diritto; **cifrati su disco** (a blocchi, con lettura a intervalli). Il file originale caricato viene eliminato dopo la conversione |
| Registro attività | database | accesso solo Admin tecnico; conservazione limitata (`AUDIT_RETENZIONE_MESI`) |
| Nomi, email, indirizzi IP e altri dati personali nel database | database | **non cifrati a livello di colonna** (servono per cercare, ordinare, accedere): vedi 3 |

L'accesso ai file avviene solo da rotte autenticate; sono pubblici soltanto logo e icona (servono alla pagina di accesso e all'app installata).

## 2. La chiave di cifratura

- `CHIAVE_CIFRATURA` è una chiave di 32 byte in base64. Si genera con:
  `docker compose exec backend python -m app.cifratura_cli genera-chiave`
- La chiave sta **solo nell'ambiente** (variabile `CHIAVE_CIFRATURA` in `.env` o nel gestore dei segreti dell'azienda), **mai nel database né nei backup dei dati**.
- **Se la chiave si perde, i dati cifrati non sono più recuperabili.** Non esiste una procedura di recupero. Per questo:
  1. conserva la chiave in almeno **due luoghi sicuri e separati** (per esempio il gestore dei segreti aziendale e una busta sigillata in cassaforte);
  2. indica **chi la custodisce** e chi può autorizzarne l'uso;
  3. **non** conservarla insieme ai backup dei dati;
  4. prova periodicamente un ripristino completo (dati + chiave) in un ambiente di prova.
- Il database memorizza un valore di verifica cifrato: all'avvio la piattaforma controlla che la chiave sia quella giusta. Se è **mancante** o **sbagliata** dopo che la cifratura è stata usata, **non si avvia** e spiega perché (meglio fermarsi che scrivere dati con la chiave sbagliata).
- `CIFRATURA_OBBLIGATORIA=true` (consigliato in produzione) impedisce l'avvio senza chiave. Senza questa impostazione la piattaforma parte anche senza cifratura (utile in sviluppo) e l'Admin tecnico vede un avviso discreto nella pagina Stato e nella pagina Informazioni.

### Attivare la cifratura
1. Genera la chiave e mettila in `CHIAVE_CIFRATURA` (e `CIFRATURA_OBBLIGATORIA=true`).
2. Riavvia: i file nuovi vengono scritti cifrati.
3. Per cifrare quanto esiste già: `docker compose exec backend python -m app.cifratura_cli cifra`
4. Verifica con `python -m app.cifratura_cli stato` (file cifrati / in chiaro). Il comando `cifra` converte anche i video già presenti.
5. Durante la conversione di un nuovo video, il file caricato e quelli di lavoro sono in chiaro sul disco per il tempo strettamente necessario e poi vengono eliminati: un disco del server cifrato (sezione 4) copre anche questo breve intervallo.

### Cambiare la chiave (rotazione)
1. Genera una nuova chiave. Metti la **vecchia** in `CHIAVI_CIFRATURA_PRECEDENTI` e la **nuova** in `CHIAVE_CIFRATURA`.
2. Riavvia, poi `python -m app.cifratura_cli ruota` (ricifra tutto con la nuova).
3. Quando `stato` non mostra più file con altra chiave, togli la vecchia da `CHIAVI_CIFRATURA_PRECEDENTI`.

### Disattivare la cifratura (emergenza o scelta)
`python -m app.cifratura_cli decifra`, poi `python -m app.cifratura_cli disattiva`, poi togli `CHIAVE_CIFRATURA`.

## 3. Dati personali nel database (nomi, email, IP...)
Cifrare queste colonne impedirebbe di cercare, ordinare e fare accedere gli utenti con le funzioni attuali; richiede indici "ciechi" e la riscrittura di molte ricerche. Per questo oggi sono protetti da:
- **cifratura del disco** del server che ospita il database (LUKS, BitLocker o equivalente del provider);
- **backup del database cifrati**, con la chiave custodita a parte;
- database **non esposto** alla rete (la piattaforma pubblica solo la porta di nginx);
- accesso al database riservato agli amministratori dell'infrastruttura.

La cifratura di queste colonne è prevista come passo dedicato prima della versione 2.0.0.

## 4. A carico di chi installa (infrastruttura)
La piattaforma non può garantire questi punti: vanno attuati dall'azienda.
- **HTTPS** davanti alla piattaforma (proxy, tunnel o bilanciatore). Il tratto tra il proxy e la porta della piattaforma (nginx, porta 2018) è in HTTP: va bene se proxy e server sono sulla stessa macchina o su un segmento di rete fidato; in una rete condivisa conviene cifrare anche quel tratto (certificato interno).
- **Cifratura del disco** del server e dei **backup**.
- **Backup** di tutti i volumi (`postgres_data`, `uploads`, `videos`) **e** custodia separata della chiave.
- Aggiornamenti del sistema operativo e di Docker; accesso SSH limitato.
- Reti e firewall: non esporre direttamente la porta 2018 a Internet.
- Un sistema di gestione dei log, se richiesto: la piattaforma può scrivere file giornalieri o righe sull'output (vedi `AUDIT_EXPORT_DIR`, `AUDIT_LOG_STDOUT` nel README).

## 5. Controlli sul codice
Ogni modifica passa da:
- una **revisione automatica** (CodeRabbit) e dalla suite di **test** (`docker compose --profile test run --rm tests`);
- **controlli di sicurezza automatici** (flusso GitHub Actions in `.github/workflows/controlli.yml`, eseguibili anche a mano con `scripts/controlli-sicurezza.sh`):
  - analisi del codice Python (**Bandit**);
  - librerie Python (**pip-audit**) e librerie del sito (**npm audit**, comprese quelle di compilazione: oggi zero vulnerabilità note);
  - immagini Docker (**Trivy**, gravità alta e critica con correzione disponibile).
- Le versioni delle librerie sono fissate (`requirements.txt`, `package-lock.json`) e le immagini non contengono strumenti di installazione (pip, setuptools) né Node in produzione.
