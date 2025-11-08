from fastapi import FastAPI
from fastapi.responses import Response
from ariadne import QueryType, MutationType, make_executable_schema
from ariadne.asgi import GraphQL
import time
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

type_defs = """
    type Event {
      id: Int!
      type: String!
      source: String!
      timestamp: String!
      status: String!
    }

    type Query {
      events: [Event!]!
      event(id: Int!): Event
    }

    type Mutation {
      publishEvent(type: String!, source: String!): Event
    }
"""

query = QueryType()
mutation = MutationType()

REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Tempo de resposta das requisições', ['endpoint'])

events_db = []

@query.field("events")
def resolve_events(*_):
    REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/events').inc()
    return events_db

@query.field("event")
def resolve_event(*_, id):
    REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/event').inc()
    for e in events_db:
        if e["id"] == id:
            return e
    return None

@mutation.field("publishEvent")
def resolve_publish_event(*_, type, source):
    start = time.perf_counter()
    REQUEST_COUNT.labels(method='GRAPHQL', endpoint='/graphql/publishEvent').inc()

    new_event = {
        "id": len(events_db) + 1,
        "type": type,
        "source": source,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "published"
    }
    events_db.append(new_event)

    REQUEST_LATENCY.labels(endpoint='/graphql/publishEvent').observe(time.perf_counter() - start)
    return new_event

schema = make_executable_schema(type_defs, [query, mutation])
app = FastAPI()
app.mount("/graphql", GraphQL(schema, debug=True))

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Quando alguém consulta eventos:
# Query events (listar todos):

# Incrementa contador de requisições
# Retorna lista completa de events_db

# Query event(id) (buscar um):

# Incrementa contador de requisições
# Busca evento por ID na lista
# Retorna evento ou null se não existir

# Quando alguém publica um evento (Mutation):

# Marca o tempo inicial
# Incrementa contador de requisições
# Cria novo evento com:

# ID automático (sequencial: 1, 2, 3...)
# Type e source informados pelo usuário
# Timestamp automático (horário atual)
# Status fixo: "published"


# Salva na lista events_db
# Registra latência
# Retorna o evento criado

# Endpoints

# /graphql: Endpoint GraphQL (queries + mutations)
# /health: Health check
# /metrics: Métricas Prometheus

# Caso de Uso
# Este código implementa Event Sourcing básico, usado em:

# Sistemas distribuídos: rastrear tudo que acontece
# Auditoria: log de todas ações do sistema
# Event-driven architecture: microsserviços publicam eventos
# CQRS: separar comandos (mutations) de consultas (queries)

# Exemplo real:

# user.created quando usuário se registra
# order.placed quando pedido é feito
# payment.processed quando pagamento confirma