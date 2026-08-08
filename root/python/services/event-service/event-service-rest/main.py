from datetime import datetime
from enum import Enum
from typing import Dict, List
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


class EventType(str, Enum):
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class EventStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


app = FastAPI(title="Event REST")

_events: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "event_http_requests_total",
    "Total de requisicoes HTTP do servico de eventos",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "event_http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de eventos",
    ["endpoint"],
)


@app.get("/all")
def get_all_events() -> List[dict]:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/all").inc()
    REQUEST_LATENCY.labels(endpoint="/all").observe(time.perf_counter() - start)
    return list(_events.values())


@app.post("/create")
def create_event(type: str, source: str) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/create").inc()

    try:
        event_type = EventType[type.upper()]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Invalid event type") from exc

    event = {
        "id": _next_id,
        "type": event_type.value,
        "source": source,
        "status": EventStatus.ENABLED.value,
        "date": datetime.now().isoformat(),
    }
    _events[_next_id] = event
    _next_id += 1
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


@app.get("/{id}")
def get_event(id: int) -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/{id}").inc()
    event = _events.get(id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    REQUEST_LATENCY.labels(endpoint="/{id}").observe(time.perf_counter() - start)
    return event
