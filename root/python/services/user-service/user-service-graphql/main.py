from fastapi import FastAPI
from fastapi.responses import Response
from ariadne import QueryType, make_executable_schema
from ariadne.asgi import GraphQL
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

type_defs = """
    type User {
      id: Int!
      name: String!
      email: String!
    }

    type Query {
      user(id: Int!): User
    }
"""

query = QueryType()

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])


@query.field("user")
def resolve_user(*_, id):
  start = time.perf_counter()
  REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/user').inc()
  resp = {"id": id, "name": f"User{id}", "email": "user@example.com"}
  REQUEST_LATENCY.labels(endpoint='/graphql/user').observe(time.perf_counter() - start)
  return resp

schema = make_executable_schema(type_defs, query)
app = FastAPI()
app.mount("/graphql", GraphQL(schema, debug=True))

@app.get("/health")
def health():
  return {"status": "ok"}


@app.get("/metrics")
def metrics():
  return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
