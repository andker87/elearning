FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt

RUN groupadd -g 1000 app && useradd -u 1000 -g app -m -s /usr/sbin/nologin app

COPY . .

# uploads/ e videos/ sono montati come volumi Docker: l'utente non-root deve
# poterci scrivere (certificati, attestati esterni, video caricati).
RUN mkdir -p /app/uploads /app/videos && chown -R app:app /app

USER app:app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
