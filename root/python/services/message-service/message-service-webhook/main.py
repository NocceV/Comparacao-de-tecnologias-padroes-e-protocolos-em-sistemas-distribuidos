from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import httpx
import time
import asyncio
import json

app = FastAPI()

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])

callbacks = []

@app.post("/hooks/messages")
async def register_hook(request: Request):
    start = time.perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid or missing JSON body")

    url = payload.get("callback_url")
    if not url:
        raise HTTPException(status_code=400, detail="callback_url required")

    callbacks.append(url)
    REQUEST_COUNT.labels(method='POST', endpoint='/hooks/messages').inc()
    REQUEST_LATENCY.labels(endpoint='/hooks/messages').observe(time.perf_counter() - start)

    return {"status": "registered", "callback": url}

@app.post("/messages")
async def create_message(request: Request):
    start = time.perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid or missing JSON body")

    message = {
        "id": 1,
        "sender": payload.get("sender", "User1"),
        "content": payload.get("content", "Mensagem padrão"),
        "timestamp": "2025-11-04T12:00:00Z"
    }

    REQUEST_COUNT.labels(method='POST', endpoint='/messages').inc()

    async def dispatch():
        async with httpx.AsyncClient() as client:
            for cb in callbacks:
                try:
                    await client.post(cb, json={"event": "message_created", "data": message})
                except Exception as e:
                    print("Falha ao enviar webhook:", e)

    asyncio.create_task(dispatch())
    REQUEST_LATENCY.labels(endpoint='/messages').observe(time.perf_counter() - start)
    return message

@app.post("/webhook/receiver")
async def receiver(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid or missing JSON body")

    print("Webhook recebido:", payload)
    return {"status": "received"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok"}
