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



# Quando alguém consulta um usuário:

# Marca o tempo inicial
# Incrementa o contador de requisições
# Cria um usuário fictício (dados mock)
# Registra o tempo total da operação
# Retorna os dados

# 4. Endpoints

# /graphql: Endpoint GraphQL principal para fazer queries
# /health: Health check (retorna {"status": "ok"})
# /metrics: Expõe métricas no formato Prometheus

# Caso de Uso
# Este código é típico de microsserviços em produção, permitindo:

# Consultar dados via GraphQL
# Monitorar performance e uso da API
# Integrar com ferramentas de observabilidade (Prometheus + Grafana)

# O usuário retornado é sempre fictício (User{id}, user@example.com), então este é um exemplo/protótipo para demonstrar a integração dessas tecnologias.