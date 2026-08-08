from datetime import datetime
from typing import Dict
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


class MessageRequest(BaseModel):
    user: str = Field(min_length=3, max_length=30)
    content: str = Field(min_length=1)


app = FastAPI(title="Message REST")

_messages: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de mensagens",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de mensagens",
    ["endpoint"],
)


@app.get("/messages/{id}")
def get_message(id: int) -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/messages/{id}").inc()
    message = _messages.get(id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    REQUEST_LATENCY.labels(endpoint="/messages/{id}").observe(time.perf_counter() - start)
    return message


@app.post("/messages/create")
def post_message(message_request: MessageRequest) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/messages/create").inc()

    message = {
        "id": _next_id,
        "user": message_request.user,
        "content": message_request.content,
        "timestamp": datetime.now().isoformat(),
    }
    _messages[_next_id] = message
    _next_id += 1
    REQUEST_LATENCY.labels(endpoint="/messages/create").observe(time.perf_counter() - start)
    return message


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
