import asyncio
from datetime import datetime
from enum import Enum
import json
import time
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


class EventType(str, Enum):
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class EventStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


app = FastAPI(title="Event SSE")

_events: Dict[int, dict] = {}
_next_id = 0
_listeners: Set[asyncio.Queue] = set()

SSE_CONNECTIONS = Counter(
    "sse_connections_total",
    "Total de conexoes SSE abertas no servico de eventos",
)
SSE_EVENTS = Counter(
    "sse_events_total",
    "Total de eventos enviados via SSE no servico de eventos",
    ["event"],
)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de eventos",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de eventos",
    ["endpoint"],
)


class EventCreate(BaseModel):
    type: Optional[str] = None
    source: Optional[str] = None


async def _broadcast(event_name: str, data: dict) -> None:
    SSE_EVENTS.labels(event=event_name).inc()
    message = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
    for queue in list(_listeners):
        await queue.put(message)


@app.get("/sse/events")
async def sse_events(request: Request):
    SSE_CONNECTIONS.inc()
    queue: asyncio.Queue = asyncio.Queue()
    _listeners.add(queue)

    async def event_generator():
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


@app.get("/all")
@app.get("/events")
def get_all_events() -> List[dict]:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/all").inc()
    REQUEST_LATENCY.labels(endpoint="/all").observe(time.perf_counter() - start)
    return list(_events.values())


@app.get("/{id}")
@app.get("/events/{id}")
def get_event(id: int) -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/{id}").inc()
    event = _events.get(id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    REQUEST_LATENCY.labels(endpoint="/{id}").observe(time.perf_counter() - start)
    return event


@app.post("/create")
@app.post("/events/create")
@app.post("/events")
async def create_event(
    body: Optional[EventCreate] = None,
    type: Optional[str] = None,
    source: Optional[str] = None,
) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/create").inc()

    event_type_str = (body.type if body and body.type else type) or ""
    event_source = (body.source if body and body.source else source) or "unknown"

    try:
        event_type = EventType[event_type_str.upper()]
    except (KeyError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid event type") from exc

    event = {
        "id": _next_id,
        "type": event_type.value,
        "source": event_source,
        "status": EventStatus.ENABLED.value,
        "date": datetime.now().isoformat(),
    }
    _events[_next_id] = event
    _next_id += 1

    await _broadcast("event_published", event)
    REQUEST_LATENCY.labels(endpoint="/create").observe(time.perf_counter() - start)
    return event


@app.patch("/status/{id}")
def update_status(id: int) -> str:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="PATCH", endpoint="/status/{id}").inc()
    event = _events.get(id)
    if event is None:
        REQUEST_LATENCY.labels(endpoint="/status/{id}").observe(time.perf_counter() - start)
        return ""

    if event["status"] == EventStatus.ENABLED.value:
        event["status"] = EventStatus.DISABLED.value
        REQUEST_LATENCY.labels(endpoint="/status/{id}").observe(time.perf_counter() - start)
        return "Evento desativado com sucesso."

    event["status"] = EventStatus.ENABLED.value
    REQUEST_LATENCY.labels(endpoint="/status/{id}").observe(time.perf_counter() - start)
    return "Evento ativado com sucesso."


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
