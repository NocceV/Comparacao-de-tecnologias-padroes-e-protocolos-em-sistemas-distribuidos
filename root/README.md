<!-- # Comparacao-de-tecnologias-padroes-e-protocolos-em-sistemas-distribuidos -->

<!-- Colocar fururamente como rodar ambiente de desenvolvimento para todos os "casos"


Ferramentas

-DrawIO para diagramas



O propósito do projeto é realizar uma análise comparativa entre seis tecnologias de comunicação em sistemas distribuídos — REST, SOAP, gRPC, WebSocket, GraphQL e Webhook — avaliando suas características, pontos fortes e limitações por meio de experimentos controlados. Para isso, o trabalho foi dividido em quatro etapas bem definidas: levantamento teórico, planejamento experimental, desenvolvimento e testes. O levantamento teórico consolidou os conceitos fundamentais sobre protocolos e padrões, suas aplicações típicas e as razões que justificam incluí-los no estudo; ele serviu de base para a definição dos serviços, das métricas e dos cenários experimentais que compõem o núcleo do planejamento. O planejamento experimental descreve os serviços que seriam implementados, os cenários de teste (ideal, realista e crítico), as métricas a serem coletadas, a instrumentação necessária e os diagramas que documentam a solução. A fase de desenvolvimento consistiu na implementação prática dos serviços nos dois ambientes escolhidos: Python, responsabilidade do Vitor, e Java, responsabilidade do Sanzio. Finalmente, a fase de testes conduziu experimentos com ferramentas de carga e monitoramento para obter dados quantitativos que deram suporte às conclusões.

O experimento foi desenhado para ser reprodutível e comparável. Para isso foram escolhidos três microserviços que representam cenários de uso distintos. O primeiro, chamado user-service, simula um serviço CRUD simples para manipulação de usuários e serve como referência para requisições pontuais e leitura/escrita típicas de APIs. O segundo, chamado message-service, simula comunicações mais orientadas a mensagens e tempo real, representando casos em que há troca contínua de dados ou notificações frequentes. O terceiro, event-service, foi pensado para cenários orientados a eventos e integrações assíncronas, especificamente para testar webhooks e entregas de eventos. Cada um desses serviços foi implementado nas linguagens definidas, de modo que existam versões em Python e em Java quando aplicável, e todos seguem um contrato funcional mínimo padronizado para permitir comparações diretas entre protocolos. O contrato padronizado define a mesma entidade base, User, com os campos id, name e email, e operações mínimas como obter usuário por id e criar usuário. As definições concretas foram documentadas no arquivo docs/api_contracts.md, que contém exemplos de endpoints REST, WSDL e operações SOAP, o arquivo proto para gRPC, queries e mutations do GraphQL, o formato de mensagens para WebSocket e a estrutura de eventos e callbacks para Webhook.

A infraestrutura experimental foi construída com contêineres Docker para assegurar isolamento, portabilidade e reprodutibilidade dos testes. Todos os serviços são empacotados com Dockerfiles e orquestrados por um docker-compose que contém os serviços de aplicação e a infraestrutura de observabilidade. A camada de monitoramento foi composta por Prometheus para coleta de métricas e Grafana para visualização, com os serviços instrumentados para expor métricas compatíveis com Prometheus. No caso do Python, a instrumentação foi planejada com a biblioteca prometheus_client, expondo métricas como contador de requisições e histograma de latências; no Java, a recomendação é utilizar Micrometer com o registrador Prometheus, ativando os endpoints do actuator para exposição das métricas. Além disso, os serviços devem registrar logs estruturados que incluam timestamps, endpoint, latência e status de resposta, favorecendo análises posteriores e correlações entre logs e métricas.

Os cenários de teste foram definidos para capturar comportamento em condições distintas. No cenário ideal a rede é estável, com latência mínima e baixa perda de pacotes; as cargas são leves para observar o comportamento de melhor caso de cada tecnologia. No cenário realista introduzimos latência e pequena perda de pacotes, juntamente com cargas moderadas que simulam o comportamento em produção típico. No cenário crítico aumentamos drasticamente a carga e pioramos as condições de rede, simulando sobrecarga, picos e degradação de conectividade para observar limites, gargalos e pontos de falha. Para simular rede degradada costuma-se usar a ferramenta netem (tc) aplicada na interface de rede do host ou dentro dos containers, permitindo parametrizar atraso, jitter e perda de pacotes de forma determinística para cada experimento.

A coleta de métricas cobre latência (tempo de resposta por requisição), throughput (requisições por segundo), consumo de CPU e memória por serviço, escalabilidade (comportamento ao aumentar número de clientes/conexões), resiliência (capacidade de recuperação perante falhas ou reinícios) e a facilidade de encontrar documentação e suporte online, que é um indicador qualitativo para adoção prática. Para execução de carga foram escolhidas ferramentas como k6 e Apache JMeter, podendo também empregar bibliotecas específicas de Python (locust) e Java para testes mais customizados; os scripts de teste devem ser versionados em /tests, com nomenclatura clara que inclua protocolo, serviço e cenário (por exemplo, k6_user_rest_ideal.js). Prometheus faz o scrape dos endpoints de métricas expostos por cada serviço, e Grafana apresenta dashboards com painéis de latência, throughput, uso de CPU e memória, e taxa de erros, permitindo comparação visual entre protocolos e cenários.

A padronização de APIs e a uniformidade dos contratos são cruciais para que as comparações sejam válidas. Para REST foi definido que a base URL é /api/users e que os endpoints mínimos são GET /users/{id}, POST /users e GET /users. As respostas seguem JSON com a mesma estrutura de campos entre implementações. Para gRPC foi definido um arquivo user.proto com as mensagens GetUserRequest, CreateUserRequest e UserResponse, e um serviço UserService contendo rpc GetUser e rpc CreateUser. Para GraphQL foi definido um endpoint /graphql contendo query user(id: Int) e a mutation createUser(name, email). Para SOAP foi proposta uma interface WSDL simples com a operação GetUser, e o endpoint SOAP expõe XML conforme o contrato. Para Webhook o servidor terá um endpoint de registro POST /hooks/users que recebe uma callback_url; quando um evento ocorrer, o servidor envia um POST para a callback com um payload padronizado do tipo { event: "user_created", data: {...}, timestamp: ... }. Para WebSocket foi definida uma rota ws://.../ws/users com mensagens JSON de ações e eventos, por exemplo action: create_user e event: user_created. Todos esses contratos estão consolidados no arquivo gerado docs/api_contracts.md que já está no repositório e pode servir como fonte de verdade para a implementação.

A organização do repositório segue uma hierarquia pensada para simplicidade e paralelismo de trabalho. No diretório raiz existe docs para diagramas e documentação, python/services que contém os serviços implementados em Python (user-service, message-service, event-service), java/services com os serviços em Java correspondentes, infra contendo docker-compose.yml e os arquivos de configuração do Prometheus e Grafana, e tests com os scripts k6/jmeter. Cada serviço possui seu Dockerfile, seu README com instruções mínimas de execução e um endpoint /health para verificação simples de integridade. O docker-compose define redes e volumes se necessários e permite subir o ambiente completo com docker-compose up --build, ou subir serviços isolados quando se deseja testar apenas um protocolo ou serviço.

A divisão de responsabilidades foi claramente atribuída para otimizar o tempo e aproveitar experiência e preferências de cada integrante. Vitor ficará responsável pela implementação em Python, contemplando REST com FastAPI ou Flask, gRPC com protoc/protobuf usando a biblioteca grpcio, GraphQL usando Ariadne ou Strawberry e WebSocket com o framework escolhido (FastAPI/uvicorn suporta websockets nativamente). Sanzio ficará responsável pela implementação em Java, utilizando Spring Boot para REST e WebSocket, JAX-WS para SOAP e mecanismos de webhook/recebimento de POSTs. Ambos implementarão versões REST de cada serviço para garantir comparabilidade entre linguagens, e cada implementação deverá expor o endpoint de métricas prometheus compatível para que Prometheus possa fazer o scrape. A comunicação entre as partes é sincronizada através do repositório Git que contém a estrutura padrão e o histórico de mudanças, e foram definidos padrões de commit e branching (branch main para release e branches de feature/xxx para desenvolvimento).

A sequência de execução prática para quem entra no projeto é: clonar o repositório, abrir a pasta do projeto, ler o README principal que contém as instruções de como construir com docker-compose, carregar os diagramas em docs/diagrams para entender a arquitetura, e executar docker-compose up --build a partir da pasta infra. Após subir os containers, verificar se os endpoints básicos respondem, por exemplo acessar /api/users/1 nos serviços REST, consultar /actuator/prometheus em serviços Java para checar métricas, ou /metrics em serviços Python se for o caso. Para rodar os testes, o usuário deve escolher um script do diretório tests/k6, ajustar as variáveis de host/port caso necessário e executar k6 run <script.js>. Os resultados do k6 podem ser exportados em JSON/CSV e, em conjunto com os dados de Prometheus, gerar painéis em Grafana que já estarão configurados a partir dos dashboards iniciais salvados em infra/grafana (se for o caso). Para simular degradação de rede, usa-se o comando tc netem ou executar netem dentro dos containers, aplicando delay e perda conforme a parametrização do cenário em testes/test_plan.md.

Quanto aos diagramas, a visão macro está representada no Diagrama de Arquitetura Geral que mostra a camada de carga (k6/JMeter), a camada de serviços (os três microserviços com as implementações em Python e Java) e a camada de monitoramento (Prometheus/Grafana), todos orquestrados no escopo de Docker. Para exames intra-fluxo existem diagramas de sequência padronizados: o diagrama de sequência para comunicação síncrona descreve o fluxo Cliente → Gateway/LoadTester → Serviço → Banco de Dados → Resposta, incluindo a exportação de métricas ao Prometheus; o diagrama de sequência para WebSocket detalha o handshake inicial (101 Switching Protocols) e a troca contínua de mensagens; o diagrama para Webhook descreve o registro do callback e o envio de eventos assíncronos do provedor para o receptor; o diagrama para GraphQL destaca o papel do resolver e a consulta seletiva de campos. Os diagramas de classe apresentam as entidades base (User, Message, Event) e os componentes típicos dos serviços (Controller, Service, Repository) para deixar claro como a lógica está organizada em ambas linguagens. Finalmente, os diagramas comparativos e o fluxograma de decisão serão produzidos a partir dos resultados para consolidar recomendações práticas.

A estratégia de testes contempla, para cada combinação protocolo × serviço, uma bateria de experimentos repetida para cenários ideal, realista e crítico. Cada experimento registra métricas primárias e secundárias e salva seus dados de saída em um diretório organizado por data, protocolo e cenário, por exemplo tests/results/k6_rest_user_ideal_20251101.json. Os dados coletados são tratados com scripts simples em Python (pandas) quando for necessário agregar e produzir as tabelas e gráficos que irão constar no relatório. A apresentação final deve incluir painéis Grafana selecionados, tabelas comparativas claras e um fluxograma de decisão que sintetize os trade-offs observados. O cronograma geral até o dia da apresentação 13/11 foi definido em marcos semanais, com a semana inicial (24/10–30/10) dedicada à estruturação e preparação do projeto, a segunda semana ao desenvolvimento dos serviços, a terceira à execução extensiva dos testes e a última à análise dos resultados e preparação dos slides. Para a semana em curso, há instruções detalhadas dia a dia que orientam desde a criação do repositório até o primeiro docker-compose com Prometheus raspando métricas, e a estratégia é priorizar primeiro a infraestrutura que permita rodar testes simples, depois instrumentar mais profundamente e só então partir para cenários críticos.

Para um novo integrante que entra no projeto é recomendável começar lendo a documentação em docs, clonando o repositório e subindo o ambiente com docker-compose. Em seguida deve abrir os diagramas da pasta docs/diagrams para ter a visão global, conferir o arquivo docs/api_contracts.md para conhecer os contratos mínimos e rodar um teste k6 simples sobre o serviço REST de referência para validar que o fluxo de testes está funcionando. Após entender essa sequência, o próximo passo é instrumentar métricas adicionais ou implementar um dos protocolos faltantes em linguagem de preferência, sempre seguindo os contratos e os padrões de logging definidos no repositório. Qualquer mudança de contrato deve ser negociada e versionada no docs/api_contracts.md e nas pastas de serviços correspondentes, e novas métricas ou dashboards em Grafana devem ser adicionados sob infra/grafana para manter rastreabilidade



#TODO

Fazer documentação 
Salvar explicações
Entender 100% de tudo
Dia 6
Dia 7 -->


# 🔗 Comparative Study of Communication Protocols and Standards

Este projeto tem como objetivo realizar uma **análise comparativa entre seis protocolos e padrões de comunicação** amplamente utilizados em sistemas distribuídos: **REST**, **SOAP**, **gRPC**, **WebSocket**, **GraphQL** e **Webhook**.  
A proposta é avaliar o desempenho, escalabilidade, resiliência e consumo de recursos de cada tecnologia sob diferentes condições de rede, auxiliando na escolha ideal de comunicação entre sistemas.

---

## 🧭 Estrutura do Projeto

O projeto foi desenvolvido de forma modular, separando os serviços por linguagem e função, garantindo flexibilidade e independência entre os componentes. A infraestrutura completa é orquestrada via **Docker Compose**.

```
📂 project-root/
├── python/
│   └── user-service/
│       ├── main.py
│       ├── requirements.txt
│       └── Dockerfile
├── java/
│   └── user-service/
│       ├── src/
│       ├── pom.xml
│       └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   └── prometheus/
│       └── prometheus.yml
├── docs/
│   ├── api_contracts.md
│   └── diagrams/
└── README.md
```

---

## ⚙️ Tecnologias Utilizadas

### **Linguagens e Frameworks**
- **Python (FastAPI)** – utilizado para construir serviços leves e rápidos, com fácil integração a Prometheus.
- **Java (Spring Boot)** – escolhido para sua robustez e uso comum em sistemas corporativos.
- **gRPC / GraphQL / WebSocket / Webhook** – implementados sobre essas bases para comparação direta de desempenho.

### **Infraestrutura e Monitoramento**
- **Docker / Docker Compose** – garante isolamento e reprodutibilidade do ambiente de testes.
- **Prometheus** – coleta métricas de desempenho (latência, throughput, uso de CPU/memória).
- **Grafana** – visualiza as métricas coletadas em dashboards dinâmicos.
- **k6 / Apache JMeter** – ferramentas utilizadas para simular carga e medir o comportamento dos serviços.

---

## 🧩 Funcionamento da Infraestrutura

A arquitetura foi planejada para permitir testes padronizados entre linguagens e protocolos.  
Cada serviço (tanto em Python quanto em Java) expõe um endpoint `/users/{id}`, com a mesma resposta em JSON, garantindo a equivalência funcional durante as medições.

O **Prometheus** é configurado para “raspar” os endpoints de métricas expostos por cada serviço, permitindo registrar informações de uso e desempenho.  
Esses dados podem ser visualizados no **Grafana**, que exibe os gráficos comparativos em tempo real.

### Fluxo geral:
1. O Docker Compose sobe todos os containers (`python_service`, `java_service`, `prometheus`, e opcionalmente `grafana`).
2. O Prometheus começa a monitorar os endpoints de métricas definidos.
3. Os serviços são testados com k6, JMeter ou scripts Python/Java customizados.
4. As métricas são salvas e comparadas entre os diferentes protocolos e padrões.

---

## 🧱 Configuração dos Serviços

### Python (FastAPI)
Arquivo `main.py`:

```python
from fastapi import FastAPI
from prometheus_client import start_http_server, Counter

app = FastAPI()
REQUESTS = Counter('requests_total', 'Total requests')
start_http_server(8001)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    REQUESTS.inc()
    return {"id": user_id, "name": f"User{user_id}", "email": "user@example.com"}
```

Arquivo `requirements.txt`:

```
fastapi
uvicorn[standard]
prometheus-client
```

Arquivo `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Java (Spring Boot)
Arquivo `Dockerfile`:

```dockerfile
FROM maven:3.8-openjdk-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package

FROM openjdk:17-jdk-slim
COPY --from=build /app/target/app.jar /app/app.jar
CMD ["java","-jar","/app/app.jar"]
```

---

## 🧠 Observabilidade

Arquivo `infra/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'python_service'
    static_configs:
      - targets: ['python_service:8001']

  - job_name: 'java_service'
    static_configs:
      - targets: ['java_service:8080']
```

Arquivo `infra/docker-compose.yml`:

```yaml
version: '3.8'
services:
  python_service:
    build: ../python/user-service
    ports:
      - "8000:8000"
    networks:
      - testnet

  java_service:
    build: ../java/user-service
    ports:
      - "8080:8080"
    networks:
      - testnet

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - testnet

networks:
  testnet:
```

---

## 🔬 Testes e Métricas

Os testes são conduzidos em três cenários distintos:

- **Ideal:** ambiente estável e com baixa latência.
- **Realista:** condições típicas de rede com variações moderadas.
- **Crítico:** alta carga, perda de pacotes e concorrência elevada.

As métricas avaliadas incluem:
- Latência (tempo de resposta)
- Throughput (requisições por segundo)
- Uso de CPU e memória
- Escalabilidade e resiliência

---

## 🧾 Histórico de Comandos e Etapas Executadas

### Dia 4 — 27/10: Configuração inicial dos serviços
```bash
cd python/user-service
pip install -r requirements.txt
uvicorn main:app --reload
# Teste local
curl http://localhost:8000/users/1
```

### Dia 5 — 28/10: Infraestrutura com Docker Compose e Prometheus
```bash
# Na pasta infra/
docker-compose up --build
# Verificação
curl http://localhost:8000/users/1
curl http://localhost:8080/users/1
# Acesso ao Prometheus
http://localhost:9090
```

---

## 📈 Próximos Passos

1. Adicionar instrumentação completa de métricas aos demais protocolos.
2. Integrar Grafana para dashboards de desempenho.
3. Executar os testes comparativos em cenários ideal, realista e crítico.
4. Gerar tabelas e gráficos de análise.

---

## 👥 Autores

**Vitor Lopes Nocce** – Implementação Python, instrumentação e análise de métricas.  
**Rafael Sanzio e Silva** – Implementação Java, integração e monitoramento.

---

## 🧩 Licença

Este projeto é de caráter **acadêmico e experimental**, desenvolvido para fins de pesquisa no contexto de análise de protocolos de comunicação em sistemas distribuídos.
