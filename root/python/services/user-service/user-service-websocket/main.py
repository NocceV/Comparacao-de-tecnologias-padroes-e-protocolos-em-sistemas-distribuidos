from typing import Dict
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


app = FastAPI(title="User WebSocket")

_users: Dict[int, dict] = {}
_next_id = 0

WS_CONNECTIONS = Counter(
    "ws_connections_total",
    "Total de conexoes WebSocket abertas no servico de usuarios",
)
WS_MESSAGES = Counter(
    "ws_messages_total",
    "Total de mensagens processadas via WebSocket no servico de usuarios",
    ["action"],
)
WS_MESSAGE_DURATION = Histogram(
    "ws_message_duration_seconds",
    "Tempo de processamento das mensagens WebSocket do servico de usuarios",
    ["action"],
)


@app.websocket("/ws/users")
async def websocket_users(websocket: WebSocket):
    global _next_id
    await websocket.accept()
    WS_CONNECTIONS.inc()
    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            data = message.get("data", {})
            start = time.perf_counter()

            if action == "create_user":
                user = {"id": _next_id, "name": data.get("name"), "email": data.get("email")}
                _users[_next_id] = user
                _next_id += 1
                await websocket.send_json({"event": "user_created", "data": user})

            elif action == "get_user":
                user = _users.get(data.get("id"))
                if user is None:
                    await websocket.send_json({"event": "user_not_found", "data": {"id": data.get("id")}})
                else:
                    await websocket.send_json({"event": "user_found", "data": user})

            else:
                await websocket.send_json({"event": "invalid_action", "data": {"action": action}})

            WS_MESSAGES.labels(action=str(action)).inc()
            WS_MESSAGE_DURATION.labels(action=str(action)).observe(time.perf_counter() - start)
    except WebSocketDisconnect:
        pass


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
