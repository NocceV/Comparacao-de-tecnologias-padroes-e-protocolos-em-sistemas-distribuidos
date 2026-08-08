from typing import Dict, List
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


app = FastAPI(title="User REST")

_users: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "user_http_requests_total",
    "Total de requisicoes HTTP do servico de usuarios",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "user_http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de usuarios",
    ["endpoint"],
)


@app.get("/user")
def get_all_users() -> List[dict]:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/user").inc()
    REQUEST_LATENCY.labels(endpoint="/user").observe(time.perf_counter() - start)
    return list(_users.values())


@app.get("/user/{id}")
def get_user(id: int) -> dict:
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="GET", endpoint="/user/{id}").inc()
    user = _users.get(id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    REQUEST_LATENCY.labels(endpoint="/user/{id}").observe(time.perf_counter() - start)
    return user


@app.post("/user/create")
def post_user(name: str, email: str) -> dict:
    global _next_id
    start = time.perf_counter()
    REQUEST_COUNT.labels(method="POST", endpoint="/user/create").inc()

    if any(existing_user["email"] == email for existing_user in _users.values()):
        raise HTTPException(status_code=409, detail="Email already exists")

    user = {"id": _next_id, "name": name, "email": email}
    _users[_next_id] = user
    _next_id += 1
    REQUEST_LATENCY.labels(endpoint="/user/create").observe(time.perf_counter() - start)
    return user


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
