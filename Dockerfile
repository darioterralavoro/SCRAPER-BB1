# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Installa solo le dipendenze di sistema minime. Non serve più JQ.
RUN apt-get update && apt-get install -y wget unzip libnss3 libgdk-pixbuf2.0-0 libgtk-3-0 libx11-xcb1 libdbus-glib-1-2 libxtst6 libxss1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# --- INIZIO SEZIONE MODIFICATA CON USER-AGENT ---

# Scarica e installa versioni fisse di Chrome e Chromedriver usando URL diretti e un User-Agent
RUN echo "Download di Chrome e Chromedriver con URL statici e User-Agent..." \
    && wget --user-agent="Mozilla/5.0" -O chrome-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.126/linux-x64/chrome-linux-x64.zip" \
    && wget --user-agent="Mozilla/5.0" -O chromedriver-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/126.0.6478.126/linux-x64/chromedriver-linux64.zip" \
    \
    && unzip chrome-linux64.zip \
    && unzip chromedriver-linux64.zip \
    \
    && mv chrome-linux64 /opt/chrome-linux64 \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    \
    && rm *.zip

# --- FINE SEZIONE MODIFICATA CON USER-AGENT ---

# Copia tutti i file del progetto
COPY . .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Esponi la porta
EXPOSE 10000

# Comando per avviare l'applicazione
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
