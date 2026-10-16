#!/usr/bin/env bash
# Controlli di sicurezza automatici, gli stessi della CI su GitHub. Servono Docker e l'accesso a Internet
# (scaricano gli strumenti e i database delle vulnerabilita'). Esce con errore se trova qualcosa.
#   scripts/controlli-sicurezza.sh            tutto
#   scripts/controlli-sicurezza.sh codice     solo analisi del codice (Bandit)
#   scripts/controlli-sicurezza.sh librerie   solo librerie Python e Node
#   scripts/controlli-sicurezza.sh immagini   solo immagini Docker (le costruisce se mancano)
set -uo pipefail
cd "$(dirname "$0")/.."
cosa="${1:-tutto}"
errori=0
passo() { echo; echo "=== $1"; }
fallito() { echo "!!! $1"; errori=$((errori + 1)); }

if [[ "$cosa" == tutto || "$cosa" == codice ]]; then
  passo "Analisi del codice Python (Bandit)"
  docker run --rm -v "$PWD/backend:/src:ro" python:3.11-slim sh -c "pip install -q bandit 2>&1 | tail -0; bandit -r /src/app -q" || fallito "Bandit ha trovato problemi"
fi

if [[ "$cosa" == tutto || "$cosa" == librerie ]]; then
  passo "Librerie Python (pip-audit)"
  docker run --rm -v "$PWD/backend:/src:ro" python:3.11-slim sh -c "pip install -q pip-audit 2>&1 | tail -0; pip-audit -r /src/requirements.txt --no-deps" || fallito "pip-audit ha trovato librerie vulnerabili"
  passo "Librerie del sito (npm audit, comprese quelle di compilazione)"
  docker run --rm -v "$PWD/frontend:/src:ro" node:20-alpine sh -c "cp -r /src /w && cd /w && npm ci --ignore-scripts >/dev/null 2>&1 && npm audit" || fallito "npm audit ha trovato librerie vulnerabili"
fi

if [[ "$cosa" == tutto || "$cosa" == immagini ]]; then
  passo "Immagini Docker (Trivy: gravita alta e critica con correzione disponibile)"
  docker compose build backend frontend >/dev/null 2>&1 || fallito "costruzione delle immagini non riuscita"
  for img in elearning-backend elearning-frontend; do
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --quiet \
      --severity HIGH,CRITICAL --ignore-unfixed --scanners vuln --exit-code 1 "$img" >/tmp/trivy-$img.txt 2>&1 \
      && echo "$img: nessuna vulnerabilita' alta o critica" || { cat /tmp/trivy-$img.txt; fallito "$img: vulnerabilita' nell'immagine"; }
  done
fi

echo
if (( errori )); then echo "RISULTATO: $errori controlli falliti"; exit 1; fi
echo "RISULTATO: tutto in ordine"
