import asyncio
from datetime import datetime
import json
import time
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


app = FastAPI(title="Message SSE")

_messages: Dict[int, dict] = {}
_next_id = 0
_listeners: Set[asyncio.Queue] = set()

SSE_CONNECTIONS = Counter(
    "sse_connections_total",
    "Total de conexoes SSE abertas no servico de mensagens",
)
SSE_EVENTS = Counter(
    "sse_events_total",
    "Total de eventos enviados via SSE no servico de mensagens",
    ["event"],
)
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


class MessageCreate(BaseModel):
    user: Optional[str] = None
    sender: Optional[str] = None
    content: Optional[str] = None


async def _broadcast(event_name: str, data: dict) -> None:
    SSE_EVENTS.labels(event=event_name).inc()
    message = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
    for queue in list(_listeners):
        await queue.put(message)


@app.get("/sse/messages")
async def sse_messages(request: Request):
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


@app.get("/messages")
def get_all_messages() -> List[dict]:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/messages").inc()
    REQUEST_LATENCY.labels(endpoint="/messages").observe(time.perf_counter() - start)
    return list(_messages.values())


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
@app.post("/messages")
async def post_message(
    body: Optional[MessageCreate] = None,
    user: Optional[str] = None,
    content: Optional[str] = None,
) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/messages/create").inc()

    sender = user
    msg_content = content

    if body:
        if body.user:
            sender = body.user
        elif body.sender:
            sender = body.sender
        if body.content:
            msg_content = body.content

    if not sender or not msg_content:
        raise HTTPException(status_code=400, detail="user/sender and content are required")

    message = {
        "id": _next_id,
        "user": sender,
        "content": msg_content,
        "timestamp": datetime.now().isoformat(),
    }
    _messages[_next_id] = message
    _next_id += 1

    await _broadcast("message_created", message)
    REQUEST_LATENCY.labels(endpoint="/messages/create").observe(time.perf_counter() - start)
    return message


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
