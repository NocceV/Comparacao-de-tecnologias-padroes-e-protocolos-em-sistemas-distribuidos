
# 🧪 Plano de Testes — Projeto de Comparação de Protocolos e Padrões de Comunicação

## 1. Objetivo
O objetivo do plano de testes é avaliar o comportamento técnico e a confiabilidade dos protocolos REST, SOAP, GraphQL, WebSocket, gRPC e Webhook em diferentes cenários de operação. A análise busca medir o desempenho sob condições ideais, realistas e críticas, considerando aspectos como latência, throughput, consumo de recursos e resiliência. Além do desempenho, os testes verificam a consistência funcional das respostas e a estabilidade das conexões em ambientes de alta carga ou falha simulada.

## 2. Escopo
Os testes serão executados sobre todos os serviços definidos no projeto, e não sobre um serviço genérico com múltiplos endpoints. Cada serviço (por exemplo, user-service, order-service, payment-service) será implementado com todos os protocolos e padrões estudados, garantindo comparações justas e abrangentes.

A infraestrutura utilizada inclui:
- Containers Docker com cada serviço isolado;
- Orquestração via Docker Compose;
- Coleta de métricas com Prometheus;
- Visualização e acompanhamento via Grafana.

## 3. Ferramentas Utilizadas
Os testes utilizarão uma combinação de ferramentas de benchmarking e observabilidade:

- Apache JMeter: para execução de testes de carga e stress (simulação de múltiplas requisições simultâneas).
- k6: para criação de cenários de carga contínua e geração de métricas de latência e throughput.
- Python scripts e Java libraries: para automação de testes específicos e simulação de falhas.
- Prometheus + Grafana: coleta e visualização de métricas em tempo real (CPU, memória, requisições, erros, uptime).
- Docker + Docker Compose: isolamento dos serviços e infraestrutura de rede simulada.

## 4. Cenários de Teste

### 4.1. Cenário Ideal
Ambiente estável com rede confiável e carga leve.
Parâmetros:
- 100 usuários virtuais
- 10 requisições/segundo
- Duração: 2 minutos
- Sem perda de pacotes (0%)
- Latência de rede média: <10 ms

Objetivo: identificar o desempenho máximo teórico de cada protocolo sem interferências externas.

### 4.2. Cenário Realista
Simula um ambiente de produção típico, com pequenas variações de rede.
Parâmetros:
- 500 usuários virtuais
- 50 requisições/segundo
- Duração: 5 minutos
- Perda de pacotes: 2–3%
- Latência média: 50–100 ms
- Variabilidade de resposta aleatória

Objetivo: avaliar estabilidade e consistência das respostas sob carga moderada.

### 4.3. Cenário Crítico
Simula ambiente degradado com falhas e alto volume de requisições.
Parâmetros:
- 2000 usuários virtuais
- 200 requisições/segundo
- Duração: 10 minutos
- Perda de pacotes: 10–15%
- Latência: 200–500 ms
- Simulação de falhas nos containers (stop/restart aleatórios)

Objetivo: testar a resiliência e recuperação dos protocolos e verificar gargalos sob pressão extrema.

## 5. Métricas Avaliadas
Durante os testes, o Prometheus coletará automaticamente:
- Tempo médio de resposta (latência)
- Throughput (requisições/s)
- Taxa de erro (%)
- Uso de CPU (%)
- Uso de memória (MB)
- Uptime e reconexões
- Logs de requisição e resposta

Os dados serão expostos via endpoints /metrics de cada serviço e armazenados no Prometheus.

## 6. Registro e Monitoramento
Os dados serão visualizados em dashboards Grafana com painéis personalizados para:
- Comparação de latência e throughput entre protocolos.
- Monitoramento de uso de CPU/memória.
- Gráficos de estabilidade (reconexões, erros e falhas).
- Logs correlacionados (via Prometheus e container logs).

## 7. Execução dos Testes
Cada protocolo será testado isoladamente com o seguinte fluxo:

1. Subir containers com `docker-compose up --build`.
2. Executar o teste de carga com:
   - `k6 run scripts/k6_rest_test.js`
   - `k6 run scripts/k6_grpc_test.js`
   - ou `jmeter -n -t tests/rest_test.jmx -l results/rest_results.csv`
3. Monitorar métricas em `http://localhost:9090` (Prometheus) e `http://localhost:3000` (Grafana).
4. Coletar dados brutos de métricas (Prometheus dump ou CSV export).

Os testes de resiliência incluirão interrupção manual dos containers durante a execução:
```bash
docker stop python_service && sleep 10 && docker start python_service
```
Isso verificará o comportamento do sistema diante de falhas temporárias.

## 8. Resultados Esperados
Os resultados serão compilados em tabelas comparativas mostrando:
- Latência média (ms)
- Throughput (req/s)
- Uso de CPU e memória
- Taxa de erro (%)
- Comportamento sob falhas

Os dados servirão de base para construir um guia de decisão sobre o uso de cada protocolo conforme o cenário.

## 9. Estrutura de Diretórios de Teste
```
project-root/
│
├── tests/
│   ├── k6/
│   │   ├── graphql_test.js
│   │   ├── grpc_test.js
│   │   └── websocket_test.js
|   |   └── webhook_test.js
│   ├── jmeter/
│   │   ├── rest_test.jmx
│   │   ├── websocket_test.jmx
│   │   └── soap_test.jmx
│   ├── scripts/
│   │   ├── fail_simulation.py
│   │   └── metrics_collector.py
│   └── results/
│       ├── raw/
│       └── processed/
│
└── infra/
    ├── docker-compose.yml
    └── prometheus/prometheus.yml
```

## 10. Formato dos Relatórios
Os relatórios conterão apenas dados brutos exportados, incluindo:
- Logs Prometheus em formato .csv
- Arquivos .json e .txt com tempos de resposta
- Dashboards Grafana salvos como .json
- Gráficos e tabelas serão gerados posteriormente na análise de resultados
