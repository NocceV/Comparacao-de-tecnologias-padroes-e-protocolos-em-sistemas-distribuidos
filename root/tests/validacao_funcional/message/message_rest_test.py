import requests
import time
import pytest

BASE_URL = "http://localhost:8012"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"
MESSAGES_URL = f"{BASE_URL}/messages"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço REST Message disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço REST Message não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_message():
    payload = {"user": "Vitor", "content": "Mensagem de teste via REST"}
    resp = requests.post(f"{MESSAGES_URL}/create", json=payload)
    assert resp.status_code == 200
    message = resp.json()
    assert message["user"] == "Vitor"
    assert message["content"] == payload["content"]

    resp_get = requests.get(f"{MESSAGES_URL}/{message['id']}")
    assert resp_get.status_code == 200
    assert resp_get.json()["content"] == payload["content"]


def test_invalid_message_rejected():
    resp = requests.post(f"{MESSAGES_URL}/create", json={"user": "ab", "content": "oi"})
    assert resp.status_code == 422


def test_get_message_not_found():
    resp = requests.get(f"{MESSAGES_URL}/999999")
    assert resp.status_code == 404


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
