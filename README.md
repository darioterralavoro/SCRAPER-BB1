# Scraper Web BB.
## Descrizione
Questa applicazione è una webapp Flask che esegue lo scraping del sito BB, raccogliendo informazioni su bonus. I dati estratti vengono visualizzati in una tabella web e possono essere scaricati in formato JSON.

## Funzionalità principali
- Avvio dello scraping tramite interfaccia web
- Visualizzazione dei risultati in tabella
- Download dei dati in formato JSON
- Log dettagliati delle operazioni di scraping

## Installazione
1. **Clona la repository o copia i file nella tua cartella di lavoro.**
2. **Crea e attiva un ambiente virtuale Python:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Installa le dipendenze:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Scarica il chromedriver compatibile con la tua versione di Chrome** e posizionalo nella cartella del progetto. Rendi il file eseguibile:
   ```sh
   chmod +x ./chromedriver
   ```

## Avvio dell'applicazione
1. Assicurati che l'ambiente virtuale sia attivo:
   ```sh
   source venv/bin/activate
   ```
2. Avvia il server Flask:
   ```sh
   python3 app.py
   ```
3. Apri il browser e vai su [http://127.0.0.1:5001](http://127.0.0.1:5001)

## Utilizzo
- Premi "Avvia Scraping" per iniziare l'estrazione dei dati.
- Attendi il completamento (può richiedere alcuni minuti).
- Visualizza i risultati nella tabella.
- Clicca su "Scarica JSON" per ottenere i dati estratti.

## Rotte disponibili
- `/` : Pagina principale con interfaccia utente
- `/start-scraping` : Avvia lo scraping (POST)
- `/results` : Restituisce lo stato e i risultati dello scraping (GET)
- `/download-json` : Scarica i risultati in formato JSON (GET)

## Struttura dei file principali
- `app.py` : Server Flask e gestione delle rotte
- `scraper.py` : Logica di scraping e parsing dei dati
- `templates/index.html` : Interfaccia utente web
- `link_map.json` : Mappatura opzionale per la sostituzione dei link
- `chromedriver` : Driver Selenium per Chrome
- `requirements.txt` : Dipendenze Python

## Sviluppi futuri suggeriti
- Esportazione dei dati anche in formato CSV
- Filtro e ricerca avanzata sui risultati nella tabella
- Gestione utenti e autenticazione
- Scheduling automatico dello scraping
- Miglioramento della gestione degli errori e notifiche all'utente
- Deploy su server remoto (ad es. con Gunicorn + Nginx)

## Note tecniche
- Il processo di scraping utilizza Selenium in modalità headless e può richiedere diversi minuti a seconda della connessione e delle performance del sito target.
- In caso di crash o blocco, riavviare il server Flask per resettare lo stato.
- Assicurati che la versione di `chromedriver` sia sempre compatibile con la versione di Chrome installata sul sistema.

---

## Regole operative AI e collaborazione

### Aggiornamento automatico della documentazione
- Ogni modifica strutturale, logica o di flusso viene documentata in questo file.
- Le regole operative, automazioni e pattern di sviluppo sono sempre aggiornati per favorire la collaborazione tra più agenti AI.

### Automazioni attive
- **Riavvio automatico Flask**: dopo ogni modifica a file HTML, JS o Python, tutti i processi Flask sulle porte 5000-5010 vengono terminati, la virtualenv viene attivata e il server Flask viene riavviato sulla porta 5001.
- **Gestione flag temporanei**: eventuali flag di scraping o lock vengono puliti automaticamente ad ogni restart.
- **Cache e reload**: la versione servita è sempre aggiornata, senza necessità di refresh forzati lato utente.

### Pattern di sviluppo e UX
- I pulsanti di mapping sono compatti e con simboli (✔️ per conferma, 🗑️ per rimuovi).
- I link già mappati sono visualizzati in readonly; per modificarli occorre prima rimuovere la mappatura.
- La logica di mapping applica solo ai link presenti e ignora quelli non trovati.
- Tutte le modifiche di UX e flusso sono descritte e tracciate in questa documentazione.

### Convenzioni e struttura
- Blueprint Flask, naming delle route e struttura dei template seguono pattern standard e sono documentati qui.
- Le dipendenze sono sempre versionate in `requirements.txt`.
- Ogni breaking change viene annotato in questa sezione.

---

**Autore:** [Tuo Nome]

Per domande o richieste di sviluppo, contattami!
