# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Installa solo le dipendenze di sistema minime.
RUN apt-get update && apt-get install -y wget unzip jq libnss3 libgdk-pixbuf2.0-0 libgtk-3-0 libx11-xcb1 libdbus-glib-1-2 libxtst6 libxss1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# --- INIZIO SEZIONE DI DEBUG VERBOSO ---

# PASSO 1: Scarica il file JSON delle versioni in un file locale.
RUN echo "PASSO 1: Download del file JSON..." \
    && wget -O versions.json "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"

# PASSO 2: Estrai l'URL di Chrome usando Python.
RUN echo "PASSO 2: Estrazione URL di Chrome con Python..." \
    && CHROME_URL=$(python -c "import json; f=open('versions.json'); data=json.load(f); print([d['url'] for d in data['channels']['Stable']['downloads']['chrome'] if d['platform']=='linux-x64'][0])") \
    && echo "URL di Chrome trovato: ${CHROME_URL}" \
    && wget -O chrome-linux64.zip "${CHROME_URL}"

# PASSO 3: Estrai l'URL di Chromedriver usando Python.
RUN echo "PASSO 3: Estrazione URL di Chromedriver con Python..." \
    && CHROMEDRIVER_URL=$(python -c "import json; f=open('versions.json'); data=json.load(f); print([d['url'] for d in data['channels']['Stable']['downloads']['chromedriver'] if d['platform']=='linux-x64'][0])") \
    && echo "URL di Chromedriver trovato: ${CHROMEDRIVER_URL}" \
    && wget -O chromedriver-linux64.zip "${CHROMEDRIVER_URL}"

# PASSO 4: Decomprimi e installa tutto.
RUN echo "PASSO 4: Installazione..." \
    && unzip chrome-linux64.zip \
    && unzip chromedriver-linux64.zip \
    && mv chrome-linux64 /opt/chrome-linux64 \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm *.zip versions.json

# --- FINE SEZIONE DI DEBUG VERBOSO ---

# Copia tutti i file del progetto
COPY . .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Esponi la porta
EXPOSE 10000

# Comando per avviare l'applicazione
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
