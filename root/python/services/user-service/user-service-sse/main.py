import asyncio
import json
import time
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


app = FastAPI(title="User SSE")

_users: Dict[int, dict] = {}
_next_id = 0
_listeners: Set[asyncio.Queue] = set()

SSE_CONNECTIONS = Counter(
    "sse_connections_total",
    "Total de conexoes SSE abertas no servico de usuarios",
)
SSE_EVENTS = Counter(
    "sse_events_total",
    "Total de eventos enviados via SSE no servico de usuarios",
    ["event"],
)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de usuarios",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de usuarios",
    ["endpoint"],
)


class UserCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


async def _broadcast(event_name: str, data: dict) -> None:
    SSE_EVENTS.labels(event=event_name).inc()
    message = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
    for queue in list(_listeners):
        await queue.put(message)


@app.get("/sse/users")
async def sse_users(request: Request):
    SSE_CONNECTIONS.inc()
    queue: asyncio.Queue = asyncio.Queue()
    _listeners.add(queue)

    async def event_generator():
        # Evento inicial de conexao estabelecida
        initial_msg = f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
        yield initial_msg
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    pass
        finally:
            _listeners.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/user")
@app.get("/users")
def get_all_users() -> List[dict]:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/user").inc()
    REQUEST_LATENCY.labels(endpoint="/user").observe(time.perf_counter() - start)
    return list(_users.values())


@app.get("/user/{id}")
@app.get("/users/{id}")
def get_user(id: int) -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/user/{id}").inc()
    user = _users.get(id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    REQUEST_LATENCY.labels(endpoint="/user/{id}").observe(time.perf_counter() - start)
    return user


@app.post("/user/create")
@app.post("/users")
async def post_user(
    body: Optional[UserCreate] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/user/create").inc()

    user_name = (body.name if body and body.name else name) or ""
    user_email = (body.email if body and body.email else email) or ""

    if not user_name or not user_email:
        raise HTTPException(status_code=400, detail="name and email are required")

    if any(existing["email"] == user_email for existing in _users.values()):
        raise HTTPException(status_code=409, detail="Email already exists")

    user = {"id": _next_id, "name": user_name, "email": user_email}
    _users[_next_id] = user
    _next_id += 1

    await _broadcast("user_created", user)
    REQUEST_LATENCY.labels(endpoint="/user/create").observe(time.perf_counter() - start)
    return user


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
