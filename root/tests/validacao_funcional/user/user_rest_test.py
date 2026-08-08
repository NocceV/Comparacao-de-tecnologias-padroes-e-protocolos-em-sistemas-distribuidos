import requests
import time
import pytest

BASE_URL = "http://localhost:8002"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"
USER_URL = f"{BASE_URL}/user"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço REST User disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço REST User não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_user():
    payload = {"name": "Rest User", "email": f"rest_user_{time.time_ns()}@example.com"}
    resp = requests.post(f"{USER_URL}/create", params=payload)
    assert resp.status_code == 200
    user = resp.json()
    assert user["name"] == payload["name"]
    assert user["email"] == payload["email"]

    resp_get = requests.get(f"{USER_URL}/{user['id']}")
    assert resp_get.status_code == 200
    assert resp_get.json()["email"] == payload["email"]


def test_list_users():
    payload = {"name": "List User", "email": f"list_user_{time.time_ns()}@example.com"}
    requests.post(f"{USER_URL}/create", params=payload)

    resp = requests.get(USER_URL)
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert payload["email"] in emails


def test_duplicate_email_conflict():
    payload = {"name": "Dup User", "email": f"dup_user_{time.time_ns()}@example.com"}
    first = requests.post(f"{USER_URL}/create", params=payload)
    assert first.status_code == 200
    second = requests.post(f"{USER_URL}/create", params=payload)
    assert second.status_code == 409


def test_get_user_not_found():
    resp = requests.get(f"{USER_URL}/999999")
    assert resp.status_code == 404


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
