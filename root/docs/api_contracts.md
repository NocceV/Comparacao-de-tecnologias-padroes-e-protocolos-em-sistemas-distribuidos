# 📘 API Contracts – Comparative Study of Communication Protocols

Este documento define o **contrato mínimo comum** entre todos os serviços e tecnologias testadas no projeto.  
O objetivo é garantir consistência entre os protocolos e possibilitar uma comparação justa em cenários idênticos.

---

## 🧩 Entidade Base: User

Todos os protocolos trabalham sobre o mesmo modelo de dados:

```json
{
  "id": 1,
  "name": "João Silva",
  "email": "joao.silva@example.com"
}
```

---

## 🌐 REST (JSON over HTTP)

**Base URL:** `/api/users`

| Método | Endpoint | Descrição | Corpo / Parâmetros | Resposta |
|--------|-----------|------------|--------------------|-----------|
| `GET` | `/users/{id}` | Retorna um usuário pelo ID | `id` (path param) | `{ "id": 1, "name": "João", "email": "joao@example.com" }` |
| `POST` | `/users` | Cria um novo usuário | `{ "name": "João", "email": "joao@example.com" }` | `{ "id": 1, "name": "João", "email": "joao@example.com" }` |
| `GET` | `/users` | Lista todos os usuários | - | `[ { ... }, { ... } ]` |

**Cabeçalhos padrão:**
```
Content-Type: application/json
Accept: application/json
```

---

## 🧼 SOAP (XML over HTTP)

Implementado em Python (FastAPI), com envelope e parsing SOAP feitos manualmente via `xml.etree.ElementTree` — não há uma biblioteca de servidor SOAP moderna e mantida para Python, então o contrato abaixo é a fonte de verdade (não segue um WSDL de terceiros).

**Endpoints:** `/soap/users` (porta 8006), `/soap/messages` (porta 8016), `/soap/events` (porta 8026)

**WSDL:** disponível via `GET` no próprio endpoint (ex: `http://localhost:8006/soap/users`)

**Operações (User):** `CreateUser(name, email)`, `GetUser(id)`

**Request:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>João</name>
      <email>joao@example.com</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>
```

**Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUserResponse>
      <id>1</id>
      <name>João</name>
      <email>joao@example.com</email>
    </CreateUserResponse>
  </soap:Body>
</soap:Envelope>
```

**Erros** (e-mail duplicado, usuário/evento não encontrado, tipo de evento inválido) retornam um `soap:Fault` com `faultcode`/`faultstring`, com o status HTTP correspondente (409/404/400).

**Operações (Message):** `CreateMessage(user, content)`, `GetMessage(id)`
**Operações (Event):** `CreateEvent(type, source)`, `GetEvent(id)`, `ToggleEventStatus(id)`

---

## ⚙️ gRPC

**Arquivo:** `user.proto`

```proto
syntax = "proto3";

package user;

service UserService {
  rpc GetUser (GetUserRequest) returns (UserResponse);
  rpc CreateUser (CreateUserRequest) returns (UserResponse);
}

message GetUserRequest {
  int32 id = 1;
}

message CreateUserRequest {
  string name = 1;
  string email = 2;
}

message UserResponse {
  int32 id = 1;
  string name = 2;
  string email = 3;
}
```

---

## 🕸️ GraphQL

**Endpoint:** `/graphql`

**Query para buscar usuário:**
```graphql
query {
  user(id: 1) {
    id
    name
    email
  }
}
```

**Mutation para criar usuário:**
```graphql
mutation {
  createUser(name: "João", email: "joao@example.com") {
    id
    name
    email
  }
}
```

---

## 🔔 Webhook

**Endpoint de registro:** `POST /hooks/users`

**Request body:**
```json
{
  "callback_url": "https://meuapp.com/events/user"
}
```

**Evento enviado pelo servidor:**
```json
{
  "event": "user_created",
  "data": {
    "id": 1,
    "name": "João",
    "email": "joao@example.com"
  },
  "timestamp": "2025-10-25T12:00:00Z"
}
```

**Resposta esperada:**
```json
{ "status": "received" }
```

---

## ⚡ WebSocket

**Endpoint:** `ws://localhost:8080/ws/users`

**Mensagens de exemplo:**

Cliente → Servidor:
```json
{
  "action": "create_user",
  "data": { "name": "João", "email": "joao@example.com" }
}
```

Servidor → Cliente:
```json
{
  "event": "user_created",
  "data": { "id": 1, "name": "João", "email": "joao@example.com" }
}
```

---

## 📊 Métricas Monitoradas (comuns a todos)

Durante os testes, todos os serviços deverão registrar:

| Métrica | Descrição | Ferramenta de Coleta |
|----------|------------|----------------------|
| `latency_ms` | Tempo médio de resposta da requisição | Prometheus + Grafana |
| `cpu_usage` | Uso médio de CPU por requisição | Docker Stats |
| `memory_usage` | Consumo de memória em MB | Prometheus |
| `throughput_rps` | Requisições por segundo | Apache JMeter / k6 |
| `resilience` | Capacidade de manter estabilidade sob carga | Logs + Monitoramento |
| `availability` | Percentual de sucesso nas requisições | Apache / k6 |

---

## 📁 Estrutura de Diretórios Recomendada

```
/docs
 └── api_contracts.md
/python
 └── services
      ├── user-service
      ├── message-service
      └── event-service
/java
 └── services
      ├── user-service
      ├── message-service
      └── event-service
```

---

**Versão:** 1.0  
**Última atualização:** 02/11/2025  
**Autores:** Vitor Lopes Nocce e Rafael Sanzio
