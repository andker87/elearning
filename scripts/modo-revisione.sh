#!/usr/bin/env bash
# Alterna il repository tra due modi per i controlli di codice.
#
#   tutto   Tutto il lavoro risulta "modifica non salvata" sul ramo master: la /code-review normale
#           (che guarda le differenze rispetto all'ultimo commit) rilegge l'intero progetto.
#   ramo    Si passa al ramo sviluppo, dove il lavoro e' in commit: /security-review e /code-review ultra
#           confrontano sviluppo con master e vedono tutto; da qui si lavora con i commit normali.
#   salva "messaggio"
#           Fa un commit su sviluppo con lo stato attuale della cartella, senza spostare il ramo corrente.
#
# Non spinge nulla su GitHub. Si ferma con un messaggio se trova modifiche che andrebbero perse.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

AUTORE_NOME="${GIT_AUTHOR_NAME:-$(git config user.name || echo 'Andrea Crestani')}"
AUTORE_EMAIL="${GIT_AUTHOR_EMAIL:-$(git config user.email || echo 'and.crestani@gmail.com')}"
corrente="$(git branch --show-current)"

IDX_TMP=""
trap 'rm -f "$IDX_TMP"' EXIT  # il file indice temporaneo sparisce anche se un comando fallisce a meta'
albero_cartella() {  # id dell'albero con TUTTO quello che c'e' nella cartella (file nuovi compresi)
  local idx; idx="$(mktemp -u)"; IDX_TMP="$idx"
  GIT_INDEX_FILE="$idx" git read-tree "$1"
  GIT_INDEX_FILE="$idx" git add -A
  GIT_INDEX_FILE="$idx" git write-tree
  rm -f "$idx"
}
pulita() { git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files -o --exclude-standard)" ]; }

case "${1:-}" in
  tutto)
    if [ "$corrente" = "master" ]; then echo "Sei già nel modo «tutto» (ramo master)."; exit 0; fi
    [ "$corrente" = "sviluppo" ] || { echo "Posizionati prima sul ramo sviluppo."; exit 1; }
    pulita || { echo "Ci sono modifiche non salvate su sviluppo: usa «salva» oppure fai un commit, poi riprova."; exit 1; }
    git checkout -q master
    git restore --source=sviluppo --staged --worktree -- .
    echo "Fatto: ramo master, tutto il lavoro come modifica non salvata. Ora /code-review rilegge l'intero progetto."
    ;;
  ramo)
    if [ "$corrente" = "sviluppo" ]; then echo "Sei già sul ramo sviluppo."; exit 0; fi
    [ "$corrente" = "master" ] || { echo "Posizionati prima su master."; exit 1; }
    [ "$(albero_cartella HEAD)" = "$(git rev-parse sviluppo^{tree})" ] || {
      echo "La cartella contiene modifiche che non sono in sviluppo. Salvale con:  scripts/modo-revisione.sh salva \"messaggio\"  e riprova."; exit 1; }
    git checkout -q -f sviluppo
    git remote set-head origin master >/dev/null 2>&1 || git update-ref refs/remotes/origin/HEAD refs/remotes/origin/master
    echo "Fatto: ramo sviluppo. /security-review e /code-review ultra vedono tutto il progetto rispetto a master."
    ;;
  salva)
    msg="${2:-}"; [ -n "$msg" ] || { echo "Serve un messaggio:  scripts/modo-revisione.sh salva \"cosa hai fatto\""; exit 1; }
    albero="$(albero_cartella sviluppo)"
    [ "$albero" != "$(git rev-parse sviluppo^{tree})" ] || { echo "Niente da salvare: sviluppo è già uguale alla cartella."; exit 0; }
    commit="$(GIT_AUTHOR_NAME="$AUTORE_NOME" GIT_AUTHOR_EMAIL="$AUTORE_EMAIL" \
      GIT_COMMITTER_NAME="$AUTORE_NOME" GIT_COMMITTER_EMAIL="$AUTORE_EMAIL" git commit-tree "$albero" -p sviluppo -m "$msg")"
    git update-ref refs/heads/sviluppo "$commit"
    echo "Salvato su sviluppo: $(git log -1 --format='%h %s' sviluppo)"
    ;;
  *) echo "Uso: scripts/modo-revisione.sh tutto | ramo | salva \"messaggio\""; exit 1 ;;
esac
