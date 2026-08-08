from datetime import datetime
from enum import Enum
from typing import Dict, List
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


class EventType(str, Enum):
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


app = FastAPI(title="Event WebSocket")

_events: Dict[int, dict] = {}
_next_id = 0
_connections: List[WebSocket] = []

WS_CONNECTIONS = Counter(
    "ws_connections_total",
    "Total de conexoes WebSocket abertas no servico de eventos",
)
WS_MESSAGES = Counter(
    "ws_messages_total",
    "Total de mensagens processadas via WebSocket no servico de eventos",
    ["action"],
)
WS_MESSAGE_DURATION = Histogram(
    "ws_message_duration_seconds",
    "Tempo de processamento das mensagens WebSocket do servico de eventos",
    ["action"],
)


async def _broadcast(payload: dict) -> None:
    dead = []
    for conn in list(_connections):
        try:
            await conn.send_json(payload)
        except Exception:
            dead.append(conn)
    for conn in dead:
        if conn in _connections:
            _connections.remove(conn)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    global _next_id
    await websocket.accept()
    WS_CONNECTIONS.inc()
    _connections.append(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            data = message.get("data", {})
            start = time.perf_counter()

            if action == "publish_event":
                try:
                    event_type = EventType[str(data.get("type", "")).upper()]
                except KeyError:
                    await websocket.send_json({"event": "invalid_event_type", "data": {"type": data.get("type")}})
                else:
                    event = {
                        "id": _next_id,
                        "type": event_type.value,
                        "source": data.get("source"),
                        "date": datetime.now().isoformat(),
                    }
                    _events[_next_id] = event
                    _next_id += 1
                    await _broadcast({"event": "event_published", "data": event})

            else:
                await websocket.send_json({"event": "invalid_action", "data": {"action": action}})

            WS_MESSAGES.labels(action=str(action)).inc()
            WS_MESSAGE_DURATION.labels(action=str(action)).observe(time.perf_counter() - start)
    except WebSocketDisconnect:
        if websocket in _connections:
            _connections.remove(websocket)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
