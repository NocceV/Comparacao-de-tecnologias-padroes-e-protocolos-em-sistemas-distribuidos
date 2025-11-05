from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import httpx
import time
import asyncio

app = FastAPI()

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])

callbacks = []

@app.post("/hooks/users")
async def register_hook(request: Request):
    start = time.perf_counter()
    payload = await request.json()
    url = payload.get("callback_url")
    if not url:
        return {"error": "callback_url required"}
    callbacks.append(url)
    REQUEST_COUNT.labels(method='POST', endpoint='/hooks/users').inc()
    REQUEST_LATENCY.labels(endpoint='/hooks/users').observe(time.perf_counter() - start)
    return {"status": "registered", "callback": url}

@app.post("/users")
async def create_user(request: Request):
    start = time.perf_counter()
    payload = await request.json()
    user = {"id": 1, "name": payload.get("name", "User1"), "email": payload.get("email", "user@example.com")}
    REQUEST_COUNT.labels(method='POST', endpoint='/users').inc()

    async def dispatch():
        async with httpx.AsyncClient() as client:
            for cb in callbacks:
                try:
                    await client.post(cb, json={"event": "user_created", "data": user})
                except Exception as e:
                    print("Failed to send webhook:", e)

    asyncio.create_task(dispatch())
    REQUEST_LATENCY.labels(endpoint='/users').observe(time.perf_counter() - start)
    return user

@app.post("/webhook/receiver")
async def receiver(request: Request):
    payload = await request.json()
    print("Webhook recebido:", payload)
    return {"status": "received"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok"}
