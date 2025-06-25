# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Installa solo le dipendenze di sistema minime, incluse quelle per Chrome headless
RUN apt-get update && apt-get install -y wget unzip jq libnss3 libgdk-pixbuf2.0-0 libgtk-3-0 libx11-xcb1 libdbus-glib-1-2 libxtst6 libxss1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Scarica e installa l'ultima versione STABILE di Chrome e il suo Chromedriver corrispondente
RUN echo "Fetching latest STABLE Chrome and Chromedriver for linux-x64..." \
    && LAST_KNOWN_GOOD_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" \
    \
    && CHROME_URL=$(wget -qO- ${LAST_KNOWN_GOOD_URL} | jq -r '.channels.Stable.downloads.chrome[] | select(.platform=="linux-x64") | .url') \
    && wget -O chrome-linux64.zip ${CHROME_URL} \
    && unzip chrome-linux64.zip \
    && mv chrome-linux64 /opt/chrome-linux64 \
    \
    && CHROMEDRIVER_URL=$(wget -qO- ${LAST_KNOWN_GOOD_URL} | jq -r '.channels.Stable.downloads.chromedriver[] | select(.platform=="linux-x64") | .url') \
    && wget -O chromedriver-linux64.zip ${CHROMEDRIVER_URL} \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    \
    && rm *.zip

# Copia tutti i file del progetto
COPY . .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Esponi la porta
EXPOSE 10000

# Comando per avviare l'applicazione
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
