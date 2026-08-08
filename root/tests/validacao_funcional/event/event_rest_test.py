import requests
import time
import pytest

BASE_URL = "http://localhost:8022"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço REST Event disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço REST Event não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_event():
    resp = requests.post(f"{BASE_URL}/create", params={"type": "publish", "source": "auth-service"})
    assert resp.status_code == 200
    event = resp.json()
    assert event["type"] == "PUBLISH"
    assert event["source"] == "auth-service"
    assert event["status"] == "ENABLED"

    resp_get = requests.get(f"{BASE_URL}/{event['id']}")
    assert resp_get.status_code == 200
    assert resp_get.json()["source"] == "auth-service"


def test_list_events():
    resp = requests.post(f"{BASE_URL}/create", params={"type": "delete", "source": "list-test"})
    assert resp.status_code == 200

    resp_all = requests.get(f"{BASE_URL}/all")
    assert resp_all.status_code == 200
    sources = [e["source"] for e in resp_all.json()]
    assert "list-test" in sources


def test_invalid_event_type_rejected():
    resp = requests.post(f"{BASE_URL}/create", params={"type": "invalid_type", "source": "x"})
    assert resp.status_code == 400


def test_toggle_event_status():
    create = requests.post(f"{BASE_URL}/create", params={"type": "update", "source": "toggle-test"})
    event_id = create.json()["id"]

    resp = requests.patch(f"{BASE_URL}/status/{event_id}")
    assert resp.status_code == 200
    assert "desativado" in resp.text.lower()

    resp2 = requests.patch(f"{BASE_URL}/status/{event_id}")
    assert resp2.status_code == 200
    assert "ativado" in resp2.text.lower()


def test_get_event_not_found():
    resp = requests.get(f"{BASE_URL}/999999")
    assert resp.status_code == 404


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "event_http_requests_total" in content
    assert "event_http_request_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
