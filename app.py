from flask import Flask, jsonify, render_template, send_file, make_response, request
from scraper import run_scraping
import threading
import io
import json
from urllib.parse import urlparse
import logging
import copy
from datetime import datetime
import re

app = Flask(__name__)

# Variabile globale per tenere traccia dei risultati
scraping_results = None
scraping_in_progress = False
current_mappings = {}
scraping_results_original = None  # Nuova variabile globale per i dati originali
scraping_lock = threading.Lock()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def index():
    # In futuro qui passeremo i risultati al template
    return render_template('index.html')

@app.route('/start-scraping', methods=['POST'])
def start_scraping_route():
    global scraping_in_progress
    data = request.get_json()
    url = (data or {}).get('url', '').strip()
    # Validazione server-side
    if not url:
        return jsonify({"status": "error", "message": "URL mancante."}), 400
    try:
        parsed = urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            raise ValueError
        if not parsed.netloc.endswith('blubonus.it'):
            return jsonify({"status": "error", "message": "Dominio non supportato. Inserisci un link di blubonus.it."}), 400
        url_pattern = r'^https?://([a-zA-Z0-9.-]+\.)?blubonus\.it([/?][^\s]*)?$'
        if not re.match(url_pattern, url):
            return jsonify({"status": "error", "message": "URL non valido o contiene caratteri non permessi."}), 400
    except Exception:
        return jsonify({"status": "error", "message": "URL non valido."}), 400
    def scraping_thread():
        global scraping_results, scraping_in_progress, scraping_results_original
        with scraping_lock:
            scraping_in_progress = True
        products, boxes = run_scraping(url)
        with scraping_lock:
            scraping_results = {
                "products": products,
                "boxes": boxes,
                "product_count": len(products),
                "box_count": len(boxes)
            }
            scraping_results_original = copy.deepcopy(scraping_results)
            scraping_in_progress = False
    thread = threading.Thread(target=scraping_thread)
    thread.start()
    return jsonify({"status": "success", "message": "Scraping avviato in background."})

@app.route('/results')
def get_results():
    with scraping_lock:
        if scraping_in_progress:
            return jsonify({"status": "running", "message": "Scraping ancora in corso..."})
        if scraping_results:
            return jsonify({"status": "completed", "data": scraping_results})
        else:
            return jsonify({"status": "no_data", "message": "Nessun risultato disponibile. Avvia prima lo scraping."})

@app.route('/download-json', methods=['POST'])
def download_json():
    global scraping_results
    with scraping_lock:
        if not scraping_results or not scraping_results.get('products'):
            return make_response('Nessun risultato disponibile.', 404)
        data = request.get_json() or {}
        selected_indices = data.get('selected_indices', [])
        products = scraping_results['products']
        if selected_indices:
            filtered_results = [products[i] for i in selected_indices if i < len(products)]
        else:
            filtered_results = products
        json_data = json.dumps(filtered_results, ensure_ascii=False, indent=2)
        buf = io.BytesIO()
        buf.write(json_data.encode('utf-8'))
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/json',
            as_attachment=True,
            download_name='prodotti_estratti.json'
        )

@app.route('/get-unique-links', methods=['GET'])
def get_unique_links():
    global scraping_results, current_mappings, scraping_results_original
    logging.debug(f"[get-unique-links] Stato scraping_results_original: {'OK' if scraping_results_original else 'None'}; Stato current_mappings: {current_mappings}")
    if not scraping_results_original or not scraping_results_original.get('products'):
        logging.warning("[get-unique-links] Nessun risultato originale disponibile per estrazione link unici.")
        return jsonify({"mapped": [], "unmapped": []})
    all_links = set()
    for product in scraping_results_original['products']:
        from scraper import extract_links_from_html
        desc_links = extract_links_from_html(product.get('Description', ''))
        all_links.update(desc_links)
        for box in product.get('Boxes', []):
            box_links = extract_links_from_html(box.get('content', ''))
            all_links.update(box_links)
    mapped = []
    unmapped = []
    for link in sorted(list(all_links)):
        if link in current_mappings and current_mappings[link]:
            mapped.append({"link": link, "replacement": current_mappings[link]})
        else:
            unmapped.append(link)
    logging.debug(f"[get-unique-links] Link mappati: {mapped}")
    logging.debug(f"[get-unique-links] Link da mappare: {unmapped}")
    return jsonify({"mapped": mapped, "unmapped": unmapped})

@app.route('/apply-mappings', methods=['POST'])
def apply_mappings():
    global scraping_results, current_mappings
    try:
        with scraping_lock:
            data = request.get_json() or {}
            if not scraping_results or not scraping_results.get('products'):
                return jsonify({'status': 'error', 'message': 'Nessun risultato disponibile.'}), 400
            mappings = data.get('mappings', {})
            if not isinstance(mappings, dict):
                return jsonify({'status': 'error', 'message': 'Formato mappatura non valido.'}), 400
            for link in list(current_mappings.keys()):
                if link not in mappings:
                    del current_mappings[link]
            for original, replacement in mappings.items():
                if replacement:
                    current_mappings[original] = replacement
                elif original in current_mappings:
                    del current_mappings[original]
            for idx, product in enumerate(scraping_results['products']):
                for original, replacement in current_mappings.items():
                    if 'Description' in product and original in product['Description']:
                        product['Description'] = product['Description'].replace(original, replacement)
                    for box in product.get('Boxes', []):
                        if 'content' in box and original in box['content']:
                            box['content'] = box['content'].replace(original, replacement)
        return jsonify({'status': 'success', 'message': 'Mappature applicate'})
    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'message': f'Errore interno: {str(e)}'}), 500

@app.route('/export-mappings-file', methods=['GET'])
def export_mappings_file():
    """Esporta le mappature correnti come file JSON scaricabile"""
    try:
        export_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_mappings": len(current_mappings),
            "mappings": current_mappings
        }
        response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
        response.headers["Content-Disposition"] = f"attachment; filename=link_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        response.headers["Content-Type"] = "application/json"
        return response
    except Exception as e:
        logging.error(f"Errore export mappings: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/import-mappings', methods=['POST'])
def import_mappings():
    global current_mappings, scraping_results_original
    try:
        imported_data = request.json
        if not imported_data or 'mappings' not in imported_data:
            return jsonify({"error": "Formato JSON non valido"}), 400
        imported_mappings = imported_data['mappings']
        # Estrai link attuali dai risultati originali
        current_links = set()
        if scraping_results_original and scraping_results_original.get('products'):
            for product in scraping_results_original['products']:
                from scraper import extract_links_from_html
                desc_links = extract_links_from_html(product.get('Description', ''))
                current_links.update(desc_links)
                for box in product.get('Boxes', []):
                    box_links = extract_links_from_html(box.get('content', ''))
                    current_links.update(box_links)
        applied_count = 0
        skipped_count = 0
        for original_link, replacement in imported_mappings.items():
            if original_link in current_links:
                current_mappings[original_link] = replacement
                applied_count += 1
                logging.info(f"Mappatura applicata: {original_link} → {replacement}")
            else:
                skipped_count += 1
                logging.debug(f"Link non trovato, mappatura ignorata: {original_link}")
        return jsonify({
            "status": "success",
            "applied": applied_count,
            "skipped": skipped_count,
            "total_current_links": len(current_links)
        })
    except Exception as e:
        logging.error(f"Errore import mappings: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/get-current-mappings', methods=['GET'])
def get_current_mappings():
    """Ritorna le mappature correnti per sincronizzazione frontend"""
    return jsonify(current_mappings)

@app.route('/reset', methods=['POST'])
def reset_scraping():
    global scraping_in_progress, scraping_results, scraping_results_original, current_mappings
    with scraping_lock:
        scraping_in_progress = False
        scraping_results = None
        scraping_results_original = None
        current_mappings.clear()
    return '', 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
