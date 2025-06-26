import csv
import json
import logging
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from tenacity import retry, stop_after_attempt, wait_fixed
import re
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, WebDriverException
import time
import hashlib
import configparser

# Configurazione del logging: livello DEBUG per dettagli
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraping.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# URL della homepage
homepage_url = "https://blubonus.it/w4yxcdlanxwp2025/"

# Header per simulare una richiesta da browser
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.114 Safari/537.36"
    )
}

CACHE_DIR = "scraping_cache"

def get_cache_duration():
    """Legge la durata della cache da config.ini, con un fallback di default."""
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        return int(config['Cache']['duration_seconds'])
    except Exception:
        return 86400

def transform_link(original_url, product_title, link_map):
    """
    Se il link originale è presente nella mappatura, restituisce il link sostituito.
    Altrimenti, lascia il link invariato e registra un messaggio di log.
    """
    if original_url in link_map:
        return link_map[original_url]
    else:
        logger.info(f"Link non presente in mappatura per scheda '{product_title}': {original_url}")
        return original_url

def clean_html_content(html_content):
    """
    Rimuove tutti gli attributi dai tag HTML, lasciando solo il contenuto testuale.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup.find_all(True):
            tag.attrs = {}
        return str(soup)
    except Exception as e:
        logger.error(f"Errore nella pulizia dell'HTML: {e}")
        return html_content

def clean_html_content_with_href(html_content, product_title, link_map):
    """
    Rimuove tutti gli attributi dai tag HTML tranne 'href' per i tag <a>.
    Esegue la sostituzione dei link.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup.find_all(True):
            if tag.name == "a":
                href = tag.get("href")
                if href:
                    transformed = transform_link(href, product_title, link_map)
                    tag.attrs = {"href": transformed}
                else:
                    tag.attrs = {}
            else:
                tag.attrs = {}
        return str(soup)
    except Exception as e:
        logger.error(f"Errore nella pulizia dell'HTML con href: {e}")
        return html_content

def extract_links_from_html(html_text):
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        links = [a.get("href") for a in soup.find_all("a", href=True)]
        return links
    except Exception as e:
        logger.error(f"Errore nell'estrazione dei link: {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_product_detail(detail_url, session, page_url, page_title, vetrina_title, product_title, category_name, index, link_map):
    try:
        prod_response = session.get(detail_url, headers=headers, timeout=10)
        if prod_response.status_code != 200:
            logger.error(f"Errore nella richiesta del prodotto {detail_url}: {prod_response.status_code}")
            return None

        detail_soup = BeautifulSoup(prod_response.text, "html.parser")
        title = product_title if product_title else ""

        # Estrazione della descrizione principale e dell'immagine
        description_elements = detail_soup.find_all("div", class_="et_pb_text_inner")
        main_description = max(
            [clean_html_content(el.decode_contents()) for el in description_elements],
            key=len, default=""
        ) if description_elements else ""

        img_tag = detail_soup.find("img", class_="wp-post-image")
        image_link = img_tag["src"] if img_tag and img_tag.get("src") else ""

        # Estrazione di tutti i box (toggle) presenti nella scheda
        toggles_in_prod = detail_soup.find_all("div", class_="et_pb_toggle")
        boxes = []
        for t in toggles_in_prod:
            toggle_title_el = t.find("h5", class_="et_pb_toggle_title")
            raw_toggle_title = toggle_title_el.decode_contents() if toggle_title_el else ""
            toggle_title = clean_html_content(raw_toggle_title) if raw_toggle_title else ""

            toggle_content_el = t.find("div", class_="et_pb_toggle_content")
            raw_toggle_content = toggle_content_el.decode_contents() if toggle_content_el else ""

            toggle_content = clean_html_content_with_href(raw_toggle_content, title, link_map) if raw_toggle_content else ""

            boxes.append({"title": toggle_title, "content": toggle_content})

        # --- Estrazione link solo per uso interno/log ---
        all_html_content = main_description + ''.join([box['content'] for box in boxes])
        found_links = extract_links_from_html(all_html_content)
        for link in found_links:
            if link not in link_map:
                logger.info(f"Link non presente in mappatura per scheda '{title}': {link}")
        # --- Fine estrazione link ---

        return {
            "Title": title,
            "Description": main_description,
            "ImageURL": image_link,
            "Boxes": boxes,
            "DetailURL": detail_url,
            "CategoryPage": page_url,
            "PageTitle": page_title,
            "Vetrina": vetrina_title,
            "CategoryName": category_name
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Errore di connessione/timeout per {detail_url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Errore generico nell'estrazione dei dettagli del prodotto {detail_url}: {e}")
        return None

def extract_products_from_page(driver, page_url, session, category_name, page_title, link_map):
    products_data = []
    try:
        logger.info(f"[SCRAPER] Apro pagina categoria: {page_url}")
        try:
            driver.get(page_url)
            # --- INIZIO BLOCCO DI LOGGING PER DEBUG REMOTO ---
            try:
                page_title = driver.title
                logger.info(f"DEBUGGING REMOTO - Titolo della pagina: '{page_title}'")
                page_source_snippet = driver.page_source[:2500]
                logger.info(f"DEBUGGING REMOTO - Anteprima HTML:\n{page_source_snippet}")
                source_lower = driver.page_source.lower()
                if "captcha" in source_lower or "verify you are human" in source_lower or "accesso negato" in source_lower:
                    logger.warning("DEBUGGING REMOTO: Rilevate parole chiave sospette (CAPTCHA/blocco) nel sorgente!")
            except Exception as e:
                logger.error(f"DEBUGGING REMOTO: Errore durante il logging di debug: {e}")
            # --- FINE BLOCCO DI LOGGING PER DEBUG REMOTO ---
        except TimeoutException:
            logger.critical(f"TIMEOUT: La pagina {page_url} ha impiegato troppo tempo a caricare e lo scraping è stato interrotto.")
            return products_data
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "et_pb_section")))
        page_source = driver.page_source
    except Exception as e:
        logger.error(f"Errore nel caricamento della pagina con Selenium {page_url}: {e}")
        return products_data

    try:
        cat_soup = BeautifulSoup(page_source, "html.parser")
    except Exception as e:
        logger.error(f"Errore nel parsing HTML della pagina {page_url}: {e}")
        return products_data

    logger.info(f"[SCRAPER] Parsing prodotti per categoria: {category_name} - {page_title}")

    # === LOGICA ORIGINALE RIPRISTINATA 1:1 ===
    # Primo metodo: raccolta dalla struttura a colonne
    columns = cat_soup.find_all("div", class_=lambda x: x and "et_pb_column" in x)
    logger.info(f"Trovate {len(columns)} colonne in {page_url}")

    product_with_vetrina = []
    for column in columns:
        vetrina_title = ""
        for tag in ["h1", "h2", "h3", "span"]:
            # Confronto case-insensitive per trovare "assegno unico"
            vetrina_tag = column.find(tag, string=lambda text: text and "assegno unico" in text.lower())
            if vetrina_tag:
                vetrina_title = vetrina_tag.get_text(strip=True)
                logger.debug(f"Colonna: trovato vetrina_title con tag {tag}: '{vetrina_title}'")
                break
        if not vetrina_title:
            # Metodo alternativo per ottenere vetrina_title, es. analizzando lo stile del tag span
            vetrina_span = column.find("span", style=lambda s: s and "color: #005baa" in s)
            vetrina_title = vetrina_span.get_text(strip=True) if vetrina_span else ""
            if vetrina_title:
                logger.debug(f"Colonna: trovato vetrina_title con 'span' style: '{vetrina_title}'")

        product_link_tags = column.find_all("a", class_="woocommerce-LoopProduct-link woocommerce-loop-product__link")
        for prod_tag in product_link_tags:
            title_tag = prod_tag.find("h2", class_="woocommerce-loop-product__title")
            product_title = title_tag.get_text(strip=True) if title_tag else ""
            product_with_vetrina.append((prod_tag, vetrina_title, product_title))

    # Secondo metodo (alternativo): ricerca diretta di link contenenti "assegno unico"
    assegno_unico_tags = cat_soup.find_all("a", string=lambda text: text and "assegno unico" in text.lower())
    for prod_tag in assegno_unico_tags:
        title_tag = prod_tag.find("h2", class_="woocommerce-LoopProduct-link woocommerce-loop-product__title")
        product_title = title_tag.get_text(strip=True) if title_tag else prod_tag.get_text(strip=True)
        if not any(p[0] == prod_tag for p in product_with_vetrina):
            product_with_vetrina.append((prod_tag, "Assegno Unico", product_title))
            logger.debug(f"Aggiunta scheda (assegno unico): {product_title}")

    # Terzo metodo (opzionale): raccolta dei link standard se non già presenti
    woocommerce_tags = cat_soup.find_all("a", class_="woocommerce-LoopProduct-link woocommerce-loop-product__link")
    for prod_tag in woocommerce_tags:
        title_tag = prod_tag.find("h2", class_="woocommerce-loop-product__title")
        product_title = title_tag.get_text(strip=True) if title_tag else prod_tag.get_text(strip=True)
        if not any(p[0] == prod_tag for p in product_with_vetrina):
            product_with_vetrina.append((prod_tag, "", product_title))
            logger.debug(f"Aggiunta scheda (woocommerce standard): {product_title}")
    # === FINE LOGICA RIPRISTINATA ===

    logger.info(f"Trovati {len(product_with_vetrina)} prodotti totali in tutta la pagina")

    indexed_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {
            executor.submit(
                get_product_detail,
                prod_tag[0].get("href"),
                session,
                page_url,
                page_title,
                prod_tag[1],
                prod_tag[2],
                category_name,
                index,
                link_map
            ): prod_tag[0].get("href")
            for index, prod_tag in enumerate(product_with_vetrina) if prod_tag[0].get("href")
        }
        for future in as_completed(future_to_url):
            result = future.result()
            if result is not None:
                indexed_results.append(result)

    return indexed_results


def run_scraping(start_url):
    # --- INIZIO LOGICA DI CACHING ---
    os.makedirs(CACHE_DIR, exist_ok=True)
    url_hash = hashlib.md5(start_url.encode('utf-8')).hexdigest()
    cache_filepath = os.path.join(CACHE_DIR, f"{url_hash}.json")
    if os.path.exists(cache_filepath):
        try:
            file_mod_time = os.path.getmtime(cache_filepath)
            if (time.time() - file_mod_time) < get_cache_duration():
                logger.info(f"Trovata cache valida per l'URL {start_url}. Caricamento dei risultati dal file.")
                with open(cache_filepath, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    return tuple(cached)
        except Exception as e:
            logger.warning(f"Impossibile leggere il file di cache {cache_filepath}: {e}. Si procederà con lo scraping.")
    # --- FINE LOGICA DI CACHING ---
    chrome_options = Options()

    # Opzioni standard
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Opzioni anti-bot
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    chrome_options.add_argument(f'user-agent={user_agent}')
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # --- Inizializzazione Semplice e Definitiva ---
    # Rimuoviamo ogni tentativo di specificare i percorsi.
    # Ci affidiamo al 100% all'ambiente configurato da Nixpacks.
    logger.info("Tentativo di avvio di Chrome con configurazione di default...")

    # Non serve più Service() perché chromedriver dovrebbe essere nel PATH
    driver = webdriver.Chrome(options=chrome_options)
    # --- Fine ---

    try:
        driver.set_page_load_timeout(300)  # Timeout massimo 5 minuti
        LINK_MAP_FILE = "link_map.json"
        link_map = {}
        if os.path.exists(LINK_MAP_FILE):
            try:
                with open(LINK_MAP_FILE, "r", encoding="utf-8") as f:
                    link_map = json.load(f)
                logger.info(f"Mappatura link caricata da {LINK_MAP_FILE}.")
            except Exception as e:
                logger.error(f"Errore nel caricamento di {LINK_MAP_FILE}: {e}")
        else:
            logger.warning(f"File {LINK_MAP_FILE} non trovato. Continuo senza trasformazioni.")

        all_products = []
        all_boxes = []

        logger.info(f"[SCRAPER] Inizio scraping URL: {start_url}")
        try:
            driver.get(start_url)
            # --- INIZIO BLOCCO DI LOGGING PER DEBUG REMOTO ---
            try:
                page_title = driver.title
                logger.info(f"DEBUGGING REMOTO - Titolo della pagina: '{page_title}'")
                page_source_snippet = driver.page_source[:2500]
                logger.info(f"DEBUGGING REMOTO - Anteprima HTML:\n{page_source_snippet}")
                source_lower = driver.page_source.lower()
                if "captcha" in source_lower or "verify you are human" in source_lower or "accesso negato" in source_lower:
                    logger.warning("DEBUGGING REMOTO: Rilevate parole chiave sospette (CAPTCHA/blocco) nel sorgente!")
            except Exception as e:
                logger.error(f"DEBUGGING REMOTO: Errore durante il logging di debug: {e}")
            # --- FINE BLOCCO DI LOGGING PER DEBUG REMOTO ---
        except TimeoutException:
            logger.critical(f"TIMEOUT: La pagina {start_url} ha impiegato troppo tempo a caricare e lo scraping è stato interrotto.")
            return [], []
        logger.info("[SCRAPER] Pagina caricata, attendo i toggle...")
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "et_pb_toggle")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        toggles = soup.find_all("div", class_="et_pb_toggle")
        main_categories = []
        for toggle in toggles:
            toggle_title_tag = toggle.find("h5", class_="et_pb_toggle_title")
            category_name = toggle_title_tag.get_text(strip=True) if toggle_title_tag else "Categoria Sconosciuta"
            content_div = toggle.find("div", class_="et_pb_toggle_content")
            if content_div:
                for a in content_div.find_all("a"):
                    href = a.get("href", "")
                    if href and ("blubonus.it" in href or href.startswith("/")):
                        full_link = urljoin(start_url, href)
                        page_title = a.get_text(strip=True)
                        main_categories.append({"category": category_name, "title": page_title, "url": full_link})
        logger.info(f"[SCRAPER] Trovate {len(main_categories)} categorie da processare.")
        if not main_categories:
            logger.warning("Nessun link di categoria trovato nei toggle. La pagina potrebbe avere una struttura diversa.")
            return [], []

        with requests.Session() as session:
            for idx, category_info in enumerate(main_categories):
                category_name = category_info["category"]
                page_title = category_info["title"]
                page_url = category_info["url"]
                logger.info(f"[SCRAPER] ({idx+1}/{len(main_categories)}) Estraggo prodotti da: '{category_name}' - '{page_title}' ({page_url})")
                products = extract_products_from_page(driver, page_url, session, category_name, page_title, link_map)
                logger.info(f"[SCRAPER] Estratti {len(products)} prodotti dalla categoria '{category_name}' - '{page_title}'")
                for product in products:
                    product_title = product.get("Title", "N/A")
                    all_products.append(product)
                    if "Boxes" in product and product["Boxes"]:
                        for box in product["Boxes"]:
                            all_boxes.append({
                                "ProductTitle": product_title,
                                "BoxTitle": box["title"],
                                "BoxContent": box["content"]
                            })
        logger.info(f"[SCRAPER] Estrazione completata. Totale prodotti: {len(all_products)}, box: {len(all_boxes)}")
        results = (all_products, all_boxes)
        try:
            with open(cache_filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            logger.info(f"Risultati per l'URL {start_url} salvati correttamente nella cache.")
        except Exception as e:
            logger.error(f"Impossibile salvare i risultati nella cache: {e}")
        return results
    except Exception as e:
        logger.error(f"Errore critico durante lo scraping dell'URL {start_url}: {e}")
        return [], []
    finally:
        logger.info("Tentativo di chiusura del driver Selenium.")
        if driver:
            try:
                driver.quit()
                logger.info("Driver chiuso con successo.")
            except Exception as e:
                logger.error(f"Errore durante la chiusura del driver: {e}")
