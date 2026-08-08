import asyncio
import json
import time

import pytest
import requests
import websockets

WS_URL = "ws://localhost:8015/ws/messages"
HEALTH_URL = "http://localhost:8015/health"
METRICS_URL = "http://localhost:8015/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço WebSocket Message disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço WebSocket Message não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_send_message_broadcast():
    async def scenario():
        content = f"Mensagem de teste {time.time_ns()}"
        async with websockets.connect(WS_URL) as sender, websockets.connect(WS_URL) as listener:
            await asyncio.sleep(0.2)
            await sender.send(json.dumps({"action": "send_message", "data": {"user": "Vitor", "content": content}}))

            sender_msg = json.loads(await sender.recv())
            listener_msg = json.loads(await listener.recv())

            assert sender_msg["event"] == "message_created"
            assert sender_msg["data"]["content"] == content
            assert listener_msg["event"] == "message_created"
            assert listener_msg["data"]["content"] == content

    asyncio.run(scenario())


def test_invalid_action():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            await socket.send(json.dumps({"action": "delete_message", "data": {}}))
            response = json.loads(await socket.recv())
            assert response["event"] == "invalid_action"

    asyncio.run(scenario())


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "ws_connections_total" in content
    assert "ws_message_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
