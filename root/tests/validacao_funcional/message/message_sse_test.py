import json
import queue
import threading
import time

import pytest
import requests

BASE_URL = "http://localhost:8017"
HEALTH_URL = f"{BASE_URL}/health"
METRICS_URL = f"{BASE_URL}/metrics"
SSE_URL = f"{BASE_URL}/sse/messages"
MESSAGE_URL = f"{BASE_URL}/messages"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço SSE Message disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SSE Message não iniciou a tempo.")


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


def test_sse_message_broadcast():
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

    # Envia nova mensagem via POST
    content = f"Mensagem SSE de teste {time.time_ns()}"
    payload = {"user": "Vitor", "content": content}
    resp = requests.post(f"{MESSAGE_URL}/create", json=payload)
    assert resp.status_code == 200
    created = resp.json()
    assert created["content"] == content

    # Verifica se o evento message_created foi transmitido via SSE
    received_event = None
    for _ in range(20):
        try:
            ev = events_q.get(timeout=0.5)
            if ev.get("event") == "message_created" and ev["data"].get("content") == content:
                received_event = ev
                break
        except queue.Empty:
            pass

    stop_ev.set()

    assert received_event is not None
    assert received_event["data"]["user"] == "Vitor"
    assert received_event["data"]["content"] == content
    print("📡 Evento message_created recebido com sucesso via SSE:", received_event)


def test_get_message():
    content = f"Busca mensagem {time.time_ns()}"
    resp = requests.post(f"{MESSAGE_URL}/create", json={"user": "Tester", "content": content})
    assert resp.status_code == 200
    mid = resp.json()["id"]

    resp_get = requests.get(f"{MESSAGE_URL}/{mid}")
    assert resp_get.status_code == 200
    assert resp_get.json()["content"] == content


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "sse_connections_total" in content
    assert "sse_events_total" in content
    assert "http_requests_total" in content
    print("📊 Métricas coletadas com sucesso!")
