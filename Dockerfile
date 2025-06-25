# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Installa le dipendenze di sistema, incluso Google Chrome
RUN apt-get update && apt-get install -y wget unzip gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Scarica e installa il chromedriver corrispondente
RUN CHROME_VERSION=$(google-chrome --version | cut -d " " -f 3 | cut -d "." -f 1-3) \
    && CD_URL=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json | grep -o "https://storage.googleapis.com/chrome-for-testing-public/[^"]*chromedriver-linux64.zip" | grep "${CHROME_VERSION}" | head -n 1) \
    && wget -O chromedriver.zip ${CD_URL} \
    && unzip chromedriver.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm chromedriver.zip chromedriver-linux64 -r

# Copia prima il file dei requisiti per sfruttare il caching di Docker
COPY requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice dell'applicazione nel container
COPY . .

# Esponi la porta su cui Gunicorn girerà
EXPOSE 10000

# Comando per avviare l'applicazione in produzione
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
