from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import time

app = FastAPI()

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    start_time = time.time()
    REQUEST_COUNT.labels(method='GET', endpoint='/users/{id}').inc()
    response = {"id": user_id, "name": f"User{user_id}", "email": "user@example.com"}
    REQUEST_LATENCY.labels(endpoint='/users/{id}').observe(time.time() - start_time)
    return response

@app.get("/metrics") 
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)