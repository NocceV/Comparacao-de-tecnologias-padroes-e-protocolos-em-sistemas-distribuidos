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

**Endpoint:** `/soap/users`

**WSDL Exemplo:** `http://localhost:8080/soap/users?wsdl`

**Operações:**
```xml
<definitions name="UserService"
    targetNamespace="http://example.com/users"
    xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:tns="http://example.com/users"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/">

  <message name="GetUserRequest">
    <part name="id" type="xsd:int"/>
  </message>

  <message name="GetUserResponse">
    <part name="user" type="tns:User"/>
  </message>

  <portType name="UserServicePortType">
    <operation name="GetUser">
      <input message="tns:GetUserRequest"/>
      <output message="tns:GetUserResponse"/>
    </operation>
  </portType>

</definitions>
```

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
