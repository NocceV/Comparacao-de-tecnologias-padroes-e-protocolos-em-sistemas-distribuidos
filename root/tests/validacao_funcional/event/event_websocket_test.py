import asyncio
import json
import time

import pytest
import requests
import websockets

WS_URL = "ws://localhost:8025/ws/events"
HEALTH_URL = "http://localhost:8025/health"
METRICS_URL = "http://localhost:8025/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço WebSocket Event disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço WebSocket Event não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_publish_event_broadcast():
    async def scenario():
        source = f"ws_test_{time.time_ns()}"
        async with websockets.connect(WS_URL) as publisher, websockets.connect(WS_URL) as subscriber:
            await asyncio.sleep(0.2)
            await publisher.send(json.dumps({"action": "publish_event", "data": {"type": "publish", "source": source}}))

            publisher_msg = json.loads(await publisher.recv())
            subscriber_msg = json.loads(await subscriber.recv())

            assert publisher_msg["event"] == "event_published"
            assert publisher_msg["data"]["source"] == source
            assert subscriber_msg["event"] == "event_published"
            assert subscriber_msg["data"]["source"] == source

    asyncio.run(scenario())


def test_invalid_event_type():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            await socket.send(json.dumps({"action": "publish_event", "data": {"type": "invalid", "source": "x"}}))
            response = json.loads(await socket.recv())
            assert response["event"] == "invalid_event_type"

    asyncio.run(scenario())


def test_invalid_action():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            await socket.send(json.dumps({"action": "delete_event", "data": {}}))
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
