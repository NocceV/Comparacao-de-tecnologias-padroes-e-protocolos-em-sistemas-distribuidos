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

@app.post("/hooks/users")
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
    REQUEST_COUNT.labels(method='POST', endpoint='/hooks/users').inc()
    REQUEST_LATENCY.labels(endpoint='/hooks/users').observe(time.perf_counter() - start)
    return {"status": "registered", "callback": url}

@app.post("/users")
async def create_user(request: Request):
    start = time.perf_counter()
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid or missing JSON body")
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



# Quando alguém cria um usuário:

# Marca o tempo inicial
# Incrementa o contador de requisições
# Cria um usuário fictício (dados mock)
# Dispara notificações assíncronas para todos os callbacks registrados
# Registra o tempo total da operação
# Retorna os dados imediatamente (sem esperar os webhooks)

# Endpoints

# /hooks/users: Registra URLs para receber notificações
# /users: Cria usuário e dispara webhooks automaticamente
# /webhook/receiver: Exemplo de endpoint que recebe notificações
# /health: Health check (retorna {"status": "ok"})
# /metrics: Expõe métricas no formato Prometheus

# Caso de Uso
# Este código é típico de arquiteturas orientadas a eventos, permitindo:

# Notificar múltiplos serviços automaticamente quando eventos ocorrem
# Desacoplar sistemas (serviços não precisam se conhecer diretamente)
# Monitorar performance e uso da API
# Processar notificações em background sem bloquear resposta

# Limitações: Os callbacks são armazenados apenas em memória (não persistem após reiniciar) e não há validação/segurança. É um exemplo/protótipo para demonstrar o padrão webhook com processamento assíncrono.