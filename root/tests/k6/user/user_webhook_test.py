import requests
import time
import pytest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# URLs principais
BASE_URL = "http://localhost:8003"
HEALTH_URL = f"{BASE_URL}/health"
HOOKS_URL = f"{BASE_URL}/hooks/users"
USERS_URL = f"{BASE_URL}/users"
METRICS_URL = f"{BASE_URL}/metrics"

# Porta e rota do mock receiver para capturar o webhook
MOCK_RECEIVER_PORT = 9999
MOCK_RECEIVER_URL = f"http://host.docker.internal:{MOCK_RECEIVER_PORT}/webhook/receiver"

# Variável global para armazenar o último payload recebido
last_webhook_payload = {}

class MockReceiverHandler(BaseHTTPRequestHandler):
    """Servidor HTTP simples para capturar chamadas de webhook."""
    def do_POST(self):
        global last_webhook_payload
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        last_webhook_payload = json.loads(post_data.decode("utf-8"))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status": "received"}')

def start_mock_receiver():
    """Inicia o servidor mock que recebe o webhook."""
    server = HTTPServer(("0.0.0.0", MOCK_RECEIVER_PORT), MockReceiverHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🔧 Mock Webhook Receiver iniciado em {MOCK_RECEIVER_URL}")

@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    """Inicia o mock receiver e valida se o serviço está disponível."""
    start_mock_receiver()
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço Webhook disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço Webhook não iniciou a tempo.")


def test_healthcheck():
    """Verifica se o endpoint /health está ativo."""
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_webhook():
    """Registra o callback do mock receiver."""
    payload = {"callback_url": MOCK_RECEIVER_URL}
    resp = requests.post(HOOKS_URL, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "registered"
    assert data["callback"] == MOCK_RECEIVER_URL


def test_create_user_and_receive_webhook():
    """Cria um usuário e verifica se o webhook é recebido."""
    global last_webhook_payload
    user_data = {"name": "WebhookUser", "email": "hook@example.com"}

    resp = requests.post(USERS_URL, json=user_data)
    assert resp.status_code == 200
    user = resp.json()
    assert user["name"] == "WebhookUser"

    # Espera até 5 segundos para o webhook ser recebido
    for _ in range(10):
        if last_webhook_payload:
            break
        time.sleep(0.5)

    assert last_webhook_payload != {}
    assert last_webhook_payload["event"] == "user_created"
    assert last_webhook_payload["data"]["email"] == "hook@example.com"
    print("📩 Webhook recebido com sucesso:", last_webhook_payload)


def test_metrics_exposed():
    """Verifica se o endpoint /metrics está expondo métricas Prometheus."""
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
