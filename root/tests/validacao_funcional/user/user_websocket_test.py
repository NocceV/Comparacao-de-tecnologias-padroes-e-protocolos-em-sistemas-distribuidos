import asyncio
import json
import time

import pytest
import requests
import websockets

WS_URL = "ws://localhost:8005/ws/users"
HEALTH_URL = "http://localhost:8005/health"
METRICS_URL = "http://localhost:8005/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço WebSocket User disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço WebSocket User não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_get_user():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            email = f"ws_user_{time.time_ns()}@example.com"
            await socket.send(json.dumps({"action": "create_user", "data": {"name": "WS User", "email": email}}))
            created = json.loads(await socket.recv())
            assert created["event"] == "user_created"
            assert created["data"]["email"] == email

            await socket.send(json.dumps({"action": "get_user", "data": {"id": created["data"]["id"]}}))
            found = json.loads(await socket.recv())
            assert found["event"] == "user_found"
            assert found["data"]["email"] == email

    asyncio.run(scenario())


def test_get_user_not_found():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            await socket.send(json.dumps({"action": "get_user", "data": {"id": 999999}}))
            response = json.loads(await socket.recv())
            assert response["event"] == "user_not_found"

    asyncio.run(scenario())


def test_invalid_action():
    async def scenario():
        async with websockets.connect(WS_URL) as socket:
            await socket.send(json.dumps({"action": "delete_user", "data": {}}))
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
