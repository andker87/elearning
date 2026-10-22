FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./

# DEV=1 aggiunge gli strumenti di test (servizio "tests" del compose); l'immagine
# normale resta senza.
ARG DEV=0
RUN pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi && \
    pip uninstall -y setuptools wheel || true

# Nell'immagine finale pip non serve piu': toglierlo elimina anche le librerie che porta con se' (e le loro segnalazioni).
RUN python -m pip uninstall -y pip

RUN groupadd -g 1000 app && useradd -u 1000 -g app -m -s /usr/sbin/nologin app

COPY . .

# uploads/ e videos/ sono montati come volumi Docker: l'utente non-root deve
# poterci scrivere (certificati, attestati esterni, video caricati).
RUN mkdir -p /app/uploads /app/videos && chown -R app:app /app

USER app:app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
