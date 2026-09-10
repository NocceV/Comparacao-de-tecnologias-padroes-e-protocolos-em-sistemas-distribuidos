import json
import queue
import threading
import time

import pytest
import requests

BASE_URL = "http://localhost:8007"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"
SSE_URL = f"{BASE_URL}/sse/users"
USER_URL = f"{BASE_URL}/user"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço SSE User disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SSE User não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _read_sse_events(url: str, event_queue: queue.Queue, stop_event: threading.Event):
    """Lê eventos da conexão SSE e insere na fila."""
    try:
        with requests.get(url, stream=True, headers={"Accept": "text/event-stream"}, timeout=10) as response:
            current_event = None
            for line in response.iter_lines(decode_unicode=True):
                if stop_event.is_set():
                    break
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
                    try:
                        data_json = json.loads(data_str)
                    except Exception:
                        data_json = data_str
                    event_queue.put({"event": current_event, "data": data_json})
    except Exception:
        pass


def test_sse_connection_and_user_broadcast():
    events_q = queue.Queue()
    stop_ev = threading.Event()

    t = threading.Thread(target=_read_sse_events, args=(SSE_URL, events_q, stop_ev), daemon=True)
    t.start()

    # Aguarda o evento de conexão inicial
    connected_event = None
    for _ in range(20):
        try:
            ev = events_q.get(timeout=0.5)
            if ev.get("event") == "connected":
                connected_event = ev
                break
        except queue.Empty:
            pass

    assert connected_event is not None
    assert connected_event["data"]["status"] == "connected"

    # Cria um novo usuário via POST
    email = f"sse_user_{time.time_ns()}@example.com"
    payload = {"name": "SSE User", "email": email}
    resp = requests.post(f"{USER_URL}/create", params=payload)
    assert resp.status_code == 200
    user_created = resp.json()
    assert user_created["email"] == email

    # Verifica se o evento user_created foi transmitido via SSE
    received_user_event = None
    for _ in range(20):
        try:
            ev = events_q.get(timeout=0.5)
            if ev.get("event") == "user_created" and ev["data"].get("email") == email:
                received_user_event = ev
                break
        except queue.Empty:
            pass

    stop_ev.set()

    assert received_user_event is not None
    assert received_user_event["data"]["name"] == "SSE User"
    assert received_user_event["data"]["email"] == email
    print("📡 Evento user_created recebido com sucesso via SSE:", received_user_event)


def test_get_user_and_list():
    email = f"sse_list_{time.time_ns()}@example.com"
    resp = requests.post(f"{USER_URL}/create", params={"name": "List SSE", "email": email})
    assert resp.status_code == 200
    uid = resp.json()["id"]

    resp_get = requests.get(f"{USER_URL}/{uid}")
    assert resp_get.status_code == 200
    assert resp_get.json()["email"] == email

    resp_all = requests.get(USER_URL)
    assert resp_all.status_code == 200
    all_emails = [u["email"] for u in resp_all.json()]
    assert email in all_emails


def test_duplicate_email_conflict():
    email = f"sse_dup_{time.time_ns()}@example.com"
    first = requests.post(f"{USER_URL}/create", params={"name": "Dup", "email": email})
    assert first.status_code == 200
    second = requests.post(f"{USER_URL}/create", params={"name": "Dup", "email": email})
    assert second.status_code == 409


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "sse_connections_total" in content
    assert "sse_events_total" in content
    assert "http_requests_total" in content
    print("📊 Métricas coletadas com sucesso!")
