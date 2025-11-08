from fastapi import FastAPI
from fastapi.responses import Response
from ariadne import QueryType, MutationType, make_executable_schema
from ariadne.asgi import GraphQL
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


type_defs = """
    type Message {
      id: Int!
      sender: String!
      content: String!
      timestamp: String!
    }

    type Query {
      message(id: Int!): Message
    }

    type Mutation {
      sendMessage(sender: String!, content: String!): Message
    }
"""

query = QueryType()
mutation = MutationType()


REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])


@query.field("message")
def resolve_message(*_, id):
    start = time.perf_counter()
    REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/message').inc()
    resp = {"id": id, "sender": "User1", "content": f"Mensagem {id}", "timestamp": "2025-11-04T12:00:00Z"}
    REQUEST_LATENCY.labels(endpoint='/graphql/message').observe(time.perf_counter() - start)
    return resp


@mutation.field("sendMessage")
def resolve_send_message(*_, sender, content):
    start = time.perf_counter()
    REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/sendMessage').inc()
    resp = {"id": 1, "sender": sender, "content": content, "timestamp": "2025-11-04T12:01:00Z"}
    REQUEST_LATENCY.labels(endpoint='/graphql/sendMessage').observe(time.perf_counter() - start)
    return resp



schema = make_executable_schema(type_defs, [query, mutation])
app = FastAPI()
app.mount("/graphql", GraphQL(schema, debug=True))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)