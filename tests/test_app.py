import pytest
from app import app, scraping_lock

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_initial_state(client):
    """Verifica che l'app parta, la rotta / funzioni e lo stato globale sia pulito."""
    response = client.get('/')
    assert response.status_code == 200
    with scraping_lock:
        from app import scraping_in_progress, scraping_results
        assert not scraping_in_progress
        assert scraping_results is None

def test_start_scraping_valid_url(monkeypatch, client):
    """Test POST /start-scraping con URL valido blubonus.it"""
    # Mock run_scraping per evitare scraping reale
    monkeypatch.setattr('app.run_scraping', lambda url: ([], []))
    response = client.post('/start-scraping', json={'url': 'https://blubonus.it/test'} )
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    # scraping_in_progress viene settato True solo nel thread, qui non possiamo garantirlo subito

def test_start_scraping_invalid_domain(client):
    """Test POST /start-scraping con dominio non supportato"""
    response = client.post('/start-scraping', json={'url': 'https://google.com/test'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Dominio non supportato' in data['message']

def test_start_scraping_malformed_url(client):
    """Test POST /start-scraping con URL malformato"""
    response = client.post('/start-scraping', json={'url': 'not_a_url'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'URL non valido' in data['message'] or 'caratteri non permessi' in data['message']

def test_reset_endpoint(monkeypatch, client):
    """Test POST /reset: resetta lo stato globale"""
    # Imposta stato sporco
    from app import scraping_in_progress, scraping_results, scraping_results_original, current_mappings
    with scraping_lock:
        scraping_in_progress = True
        scraping_results = {'products': [{'data': 'test'}]}
        scraping_results_original = {'products': [{'data': 'test'}]}
        current_mappings.clear()
        current_mappings['a'] = 'b'
    # Mock reset_scraping se serve
    if hasattr(app, 'reset_scraping'):
        monkeypatch.setattr('app.reset_scraping', lambda: None)
    response = client.post('/reset')
    assert response.status_code == 200
    # Verifica stato pulito
    with scraping_lock:
        from app import scraping_in_progress, scraping_results, scraping_results_original, current_mappings
        assert not scraping_in_progress
        assert scraping_results is None
        assert scraping_results_original is None
        assert current_mappings == {}

def test_apply_mappings(monkeypatch, client):
    """Test POST /apply-mappings usando monkeypatch per un corretto setup dello stato."""
    import app
    initial_results = {
        'products': [
            {'Title': 'Prodotto A', 'Description': 'link: http://example.com/a', 'Boxes': []},
            {'Title': 'Prodotto B', 'Description': 'link: http://example.com/b', 'Boxes': []}
        ]
    }
    monkeypatch.setattr(app, 'scraping_results', initial_results)
    monkeypatch.setattr(app, 'scraping_results_original', initial_results.copy())
    monkeypatch.setattr(app, 'current_mappings', {})
    mappings_payload = {
        'mappings': {'http://example.com/a': 'http://nuovo-link.com/a-modificato'}
    }
    response = client.post('/apply-mappings', json=mappings_payload)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
    assert 'http://nuovo-link.com/a-modificato' in app.scraping_results['products'][0]['Description']
    assert 'http://nuovo-link.com/a-modificato' in app.current_mappings.values()

def test_download_json(monkeypatch, client):
    """Test POST /download-json usando monkeypatch per un corretto setup dello stato."""
    # Importa il modulo 'app'
    import app

    # Stato iniziale controllato
    test_data = {
        'products': [
            {'Title': 'Test Download', 'Description': 'link: http://link.test', 'Boxes': []}
        ]
    }
    # Imposta lo stato globale che l'endpoint /download-json leggerà
    monkeypatch.setattr(app, 'scraping_results', test_data)
    monkeypatch.setattr(app, 'scraping_results_original', test_data.copy())

    # Esegui la richiesta POST
    response = client.post('/download-json', json={})

    # Asserzioni su status e header (invariate)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'

    # Decodifica la risposta JSON
    exported_data = response.get_json()

    # VERIFICA CORRETTA: La risposta è una lista, accediamo direttamente al primo elemento.
    assert isinstance(exported_data, list)
    assert exported_data[0]['Title'] == 'Test Download'
