# Storico del progetto

Questo repository ha una **cronologia ricostruita**, e conviene saperlo prima di leggerla.

## Cos'è e cosa non è
Le versioni 1.0.0 → 1.8.2 sono state sviluppate di seguito, in pochi giorni, senza salvare un commit a ogni passo. La cronologia qui sotto è stata **ricostruita a posteriori**, dividendo il lavoro in un commit per fase:

- ogni commit contiene i file *nati* in quella fase, secondo la loro **data di creazione reale**, con il contenuto della **versione finale**;
- i file già esistenti e modificati stanno nella fase della loro ultima modifica (se è molto recente, nella 1.1.0, la prima che li ha toccati);
- le **date** dei commit sono quelle di creazione o ultima modifica dei file, non di una registrazione fedele dei passaggi;
- il testo di ogni commit riprende il changelog della versione.

Quindi: i commit intermedi dicono *in quale ordine e quando* sono nate le parti, non *com'era il codice quel giorno*. Gli stati intermedi **non sono eseguibili né testati**. Solo la punta del ramo lo è (227 test automatici). Dopo l'ultimo commit ricostruito, ogni commit è un salvataggio reale.

Le etichette (`v1.0.0` … `v1.8.2`) segnano le fasi; le versioni 1.4.1/1.4.2, 1.5.0/1.5.1 e 1.7.0/1.7.1 sono nello stesso commit perché i file che le distinguono non si separano.

## Le fasi
| Commit | Data | Versione e contenuto |
|---|---|---|
| `2833d49` | 21/09/2026 12:14 | Initial commit |
| `88a76cb` | 12/10/2026 14:47 | 1.0.0: Piattaforma completa |
| `2390a12` | 12/10/2026 17:28 | 1.1.0: Accesso aziendale e audit esteso |
| `c3344fc` | 13/10/2026 07:42 | 1.2.0: Uniformità di menu, impostazioni e privacy |
| `dc399b5` | 13/10/2026 10:58 | 1.2.1: Privacy come strumento aziendale |
| `59b8fd9` | 13/10/2026 11:52 | 1.3.0: Accessi sicuri, matrice e pacchetto per l'ispezione |
| `f8baacf` | 13/10/2026 12:29 | 1.4.0: Sincronizzazione utenti e test automatici |
| `5e07715` | 13/10/2026 13:56 | 1.4.1 e 1.4.2: Fabbisogno formativo: scelte chiare e vista della Formazione |
| `3eeee35` | 14/10/2026 10:27 | 1.5.0 e 1.5.1: Rinnovo automatico dei corsi e pagine a tutta larghezza |
| `54275a6` | 14/10/2026 11:56 | 1.6.0: Fusione delle richieste e configurazione portabile |
| `974b1e0` | 14/10/2026 12:33 | 1.7.0 e 1.7.1: Etichette dei corsi e filtri |
| `31be53c` | 14/10/2026 12:57 | 1.7.2: Correzioni dalla revisione del codice |
| `58fda25` | 14/10/2026 14:29 | 1.8.0: Migrazioni, IP affidabili, inviti senza password |
| `c4a4193` | 14/10/2026 14:48 | 1.8.1: Correzioni dalla seconda revisione del codice |
| `fbd0384` | 14/10/2026 16:07 | 1.8.2: Correzioni dalla terza revisione e documentazione |

Il primo commit (21/09/2026) è il punto di partenza, precedente alle versioni numerate.

## Come si lavora ora
- Il ramo di lavoro è **`sviluppo`**; `master` resta al primo commit.
- `scripts/modo-revisione.sh` passa da un modo all'altro per i controlli del codice:
  - `tutto`: sul ramo `master` tutto il lavoro risulta modifica non salvata, così `/code-review` rilegge l'intero progetto;
  - `ramo`: si torna su `sviluppo`, dove `/security-review` e `/code-review ultra` confrontano il ramo con `master` e vedono tutto;
  - `salva "messaggio"`: commit su `sviluppo` dello stato attuale della cartella.
- Da quando l'intero progetto è stato riletto, si lavora su `sviluppo` con commit normali: ogni `/code-review` guarda solo le modifiche nuove.

Documenti correlati: [`ROADMAP.md`](../ROADMAP.md) (storia e decisioni, con le date) e il changelog nella pagina *Informazioni* dell'app.
