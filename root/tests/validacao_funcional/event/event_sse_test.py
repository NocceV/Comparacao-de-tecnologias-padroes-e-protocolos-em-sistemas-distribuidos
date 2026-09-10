import json
import queue
import threading
import time

import pytest
import requests

BASE_URL = "http://localhost:8027"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"
SSE_URL = f"{BASE_URL}/sse/events"
EVENT_URL = f"{BASE_URL}/events"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço SSE Event disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SSE Event não iniciou a tempo.")


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


def test_sse_event_broadcast():
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

    # Publica novo evento via POST
    source = f"sse_test_source_{time.time_ns()}"
    payload = {"type": "PUBLISH", "source": source}
    resp = requests.post(f"{BASE_URL}/create", params=payload)
    assert resp.status_code == 200
    created = resp.json()
    assert created["source"] == source

    # Verifica se o evento event_published foi transmitido via SSE
    received_event = None
    for _ in range(20):
        try:
            ev = events_q.get(timeout=0.5)
            if ev.get("event") == "event_published" and ev["data"].get("source") == source:
                received_event = ev
                break
        except queue.Empty:
            pass

    stop_ev.set()

    assert received_event is not None
    assert received_event["data"]["type"] == "PUBLISH"
    assert received_event["data"]["source"] == source
    print("📡 Evento event_published recebido com sucesso via SSE:", received_event)


def test_invalid_event_type():
    resp = requests.post(f"{BASE_URL}/create", params={"type": "INVALIDO", "source": "test"})
    assert resp.status_code == 400


def test_update_status():
    resp = requests.post(f"{BASE_URL}/create", params={"type": "DELETE", "source": "status_test"})
    assert resp.status_code == 200
    eid = resp.json()["id"]

    resp_patch = requests.patch(f"{BASE_URL}/status/{eid}")
    assert resp_patch.status_code == 200
    assert "desativado" in resp_patch.text

    resp_patch2 = requests.patch(f"{BASE_URL}/status/{eid}")
    assert resp_patch2.status_code == 200
    assert "ativado" in resp_patch2.text


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "sse_connections_total" in content
    assert "sse_events_total" in content
    assert "http_requests_total" in content
    print("📊 Métricas coletadas com sucesso!")
