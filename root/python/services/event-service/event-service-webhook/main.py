from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import httpx
import asyncio
import time
import json

app = FastAPI(title="Event Service - Webhook")

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])
EVENT_DISPATCH_COUNT = Counter('webhook_event_dispatch_total', 'Eventos enviados para callbacks')

callbacks = []

@app.post("/hooks/events")
async def register_event_hook(request: Request):
    start = time.perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    url = payload.get("callback_url")
    if not url:
        raise HTTPException(status_code=400, detail="callback_url required")
    
    callbacks.append(url)
    REQUEST_COUNT.labels(method='POST', endpoint='/hooks/events').inc()
    REQUEST_LATENCY.labels(endpoint='/hooks/events').observe(time.perf_counter() - start)
    return {"status": "registered", "callback": url}


@app.post("/events")
async def create_event(request: Request):
    start = time.perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event = {
        "id": int(time.time()),
        "type": payload.get("type", "generic_event"),
        "source": payload.get("source", "event-service"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "emitted"
    }
    REQUEST_COUNT.labels(method='POST', endpoint='/events').inc()

    async def dispatch():
        async with httpx.AsyncClient() as client:
            for cb in callbacks:
                try:
                    await client.post(cb, json={"event": event})
                    EVENT_DISPATCH_COUNT.inc()
                except Exception as e:
                    print("Failed to send event to:", cb, "Error:", e)

    asyncio.create_task(dispatch())
    REQUEST_LATENCY.labels(endpoint='/events').observe(time.perf_counter() - start)
    return {"status": "event emitted", "event": event}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "ok"}
