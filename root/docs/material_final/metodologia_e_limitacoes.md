# Metodologia, Parâmetros e Limitações (versão final)

> Documento de apoio para a redação do artigo. Descreve **exatamente** como cada número foi produzido, o que mudou
> em relação à versão anterior dos testes e quais são as limitações conhecidas (úteis para a seção de ameaças à validade).

## 1. Infraestrutura — mesma capacidade para todas as tecnologias

Arquivo: `infra/docker-compose.yml` (bloco `x-service-limits`, aplicado aos 21 serviços via `<<: *service-limits`).

| Recurso | Valor por contêiner de serviço |
|---|---|
| CPU | **0,5 vCPU** (`cpus: "0.50"`, quota CFS de 50 ms a cada 100 ms) |
| Memória | **256 MiB** (`mem_limit: 256m`) |
| Swap | desabilitado (`memswap_limit = mem_limit`) |
| PIDs | 256 |

* São 21 contêineres de serviço (3 domínios × 7 tecnologias), todos com cota **idêntica**; foi conferido via
  `docker inspect` (campos `NanoCpus`, `Memory`, `MemorySwap`, `PidsLimit`) e o resultado está em `manifest.json` e
  `containers_after.json` de cada cenário (inclui `OOMKilled` e `RestartCount` para provar que nenhum contêiner foi
  encerrado por falta de memória durante os testes).
* Prometheus e Grafana (observação) têm limites próprios (1 vCPU / 512 MiB) e não fazem parte da comparação.
* Efeito colateral esperado: como a cota (0,5 vCPU) é menor que a do ambiente anterior (sem limite), as latências
  absolutas **não são comparáveis** com a versão anterior do artigo; todas as tabelas foram regeradas.

## 2. Cenários (derivados de `docs/test_plan.md`)

Os três cenários combinam degradação de rede (emulada com `tc netem`) e nível de carga.

| Cenário | Atraso adicionado | Perda de pacotes | Clientes simultâneos (regime estocástico e CPU/RAM) |
|---|---|---|---|
| Ideal | nenhum | 0 % | 1 (sequencial) |
| Realista | 75 ± 25 ms (50–100 ms, uniforme) | 2,5 % (ponto médio de 2–3 %) | 10 |
| Crítico | 350 ± 150 ms (200–500 ms, uniforme) | 12,5 % (ponto médio de 10–15 %) | 50 |

* O regime **determinístico** é sempre sequencial (1 cliente) em todos os cenários: isola o efeito da rede.
* O regime **estocástico** e a medição de **CPU/RAM** aplicam também a carga simultânea do cenário.
* Implementação da rede: um contêiner auxiliar (`tc-sidecar`, Alpine + `iproute2`) compartilha o *namespace* de rede de
  cada serviço e executa `tc qdisc replace dev eth0 root netem delay Xms Yms loss Z%`. Nenhuma imagem de serviço foi alterada.
* **Limitação:** o `netem` atua na interface de **saída** do serviço (caminho de **resposta** servidor→cliente). O atraso
  configurado equivale ao acréscimo de RTT; a perda de respostas/ACKs provoca retransmissões TCP (RTO) no servidor. O
  caminho cliente→servidor não é degradado (o cliente roda no host Windows).
* **Desvios em relação ao plano original:** o plano prevê 100/500/2000 usuários virtuais e 2/5/10 minutos com k6/JMeter.
  O ambiente (Docker Desktop no Windows, geradores Python) não sustenta 2000 usuários virtuais; a carga foi **escalonada**
  (1/10/50 clientes simultâneos) e a duração é definida por número fixo de requisições (igual para todas as tecnologias).
  O k6 não está instalado neste ambiente; os scripts k6 existentes em `tests/k6/` permanecem como referência.

## 3. Garantia de igualdade de requisições entre tecnologias

| Fase | Requisições por tecnologia | Detalhe |
|---|---|---|
| Aquecimento (não medido) | 9 (3 por serviço) por fase | idêntico para todas |
| Determinístico | **300** | 100 por serviço, sequenciais |
| Estocástico | **30** (14,29 % da carga) | 10 por serviço; total 210; ordem embaralhada (semente 42) |
| CPU/RAM | **300** | 100 por serviço |

O JSON de cada fase registra `requests`, `success` e `errors` por tecnologia; as tabelas mostram a contagem e o
percentual (14,3 % para todas no estocástico). O Prometheus (contadores `*_requests_total`, `ws_messages_total`) permite
conferir a contagem do lado do servidor (`tab_telemetria_prometheus.tex`).

## 4. Semântica do cliente por tecnologia (importante para interpretar as latências)

| Tecnologia | Como o cliente se comporta | O que entra no tempo medido |
|---|---|---|
| REST, SOAP, GraphQL, Webhook, SSE | `requests.post` **sem** sessão: nova conexão TCP a cada requisição | handshake TCP + requisição + resposta |
| WebSocket | uma nova conexão por requisição; **o tempo é cronometrado só após a conexão aberta** | envio + resposta da mensagem |
| gRPC | **canal persistente** (HTTP/2) reaproveitado entre chamadas | chamada RPC (a 1ª chamada inclui a criação do canal, se não houver aquecimento) |

Consequência: WebSocket e gRPC não pagam o custo de conexão no tempo medido, enquanto as tecnologias HTTP pagam.
Isso reflete o modo de uso típico (conexão persistente × requisição-resposta), mas deve ser mencionado como limitação.
Timeout de 5 s por requisição (falhas e *timeouts* contam como erro e entram na taxa de sucesso).

## 5. Operações executadas (paridade funcional)

| Serviço | REST / SOAP / Webhook / SSE / WebSocket | GraphQL | gRPC |
|---|---|---|---|
| user | criar usuário (escrita) | `query user(id)` (leitura, dado simulado) | `GetUser` (leitura, dado simulado) |
| message | criar mensagem (escrita) | `query message(id)` (leitura) | `SendMessage` (escrita) |
| event | criar/publicar evento (escrita) | `query event(id)` (leitura) | `EmitEvent` (escrita) |

**Limitação conhecida (herdada do desenho dos serviços):** nos serviços *user* (GraphQL/gRPC) e nos GraphQL de
*message*/*event* a operação medida é de **leitura** de dado simulado, enquanto nas demais tecnologias é de **escrita em
memória**. As diferenças de latência absolutas entre tecnologias devem ser lidas com essa ressalva. O contrato dos
serviços (`docs/api_contracts.md`) não foi alterado nesta versão.

## 6. Definições estatísticas

* **Latência média / mediana / desvio-padrão (amostral) / p95 / p99 / mín / máx**: calculadas apenas sobre requisições
  **bem-sucedidas**; percentis por interpolação linear (mesma definição do `numpy.percentile` padrão).
* **Consolidação por tecnologia**: amostra agrupada (*pooled*) das 300 requisições (média ponderada correta).
* **Vazão total** = requisições disparadas ÷ tempo decorrido; **vazão útil (*goodput*)** = respostas bem-sucedidas ÷ tempo.
  A vazão consolidada por tecnologia é **Σ requisições ÷ Σ tempos** (média harmônica das vazões por serviço).
  *Mudança em relação à versão anterior*, que usava a média aritmética das três vazões — por isso os números diferem
  ligeiramente mesmo em condições iguais.
* **Taxa de sucesso** = sucessos ÷ requisições disparadas.

## 7. Medição de CPU e memória

* Fonte: contadores cumulativos de cgroup lidos pela **API do Docker Engine** (nada é executado dentro dos contêineres
  medidos → sem overhead de medição).
* **CPU líquida (ms/req.)** = (Δ tempo de CPU na janela de carga − taxa ociosa × duração) ÷ nº de requisições.
  A taxa ociosa é medida em uma janela de 10 s sem carga (inclui o *scraping* do Prometheus a cada 5 s).
* **CPU para 100 req/s (% de 1 vCPU)** = CPU líquida (ms/req.) × 10 (derivado: 100 req/s × ms/req ÷ 1000 × 100 %).
* **Throttling**: Δ de períodos CFS limitados (indica que o serviço atingiu o teto de 0,5 vCPU).
* **Memória**: *working set* (`usage − inactive_file`, mesma definição do `docker stats`), somada nos 3 contêineres da
  tecnologia, amostrada a ~7 Hz durante a carga (ociosa, média, pico e crescimento).
* Medimos em cada um dos três cenários, com a mesma carga (500 req./serviço, 8 clientes simultâneos).

## 8. Resiliência a falhas de conexão (`tests/scripts/resilience_test.py`)

Cliente a 10 req/s, timeout de 2 s, janela de 30 s; a falha é injetada aos 8 s:
**blackout** (100 % de perda das respostas por 6 s via `netem`) e **reinício** do contêiner (`docker restart`).
WebSocket usa uma conexão persistente com reconexão sob demanda; gRPC usa um canal persistente com o *backoff* padrão
da biblioteca e uma variante com *backoff* limitado a 100 ms–1 s. As demais tecnologias abrem uma conexão por requisição.

## 9. Experimento controlado do gRPC (`tests/scripts/grpc_variation_experiment.py`)

Mede, na rede ideal, 10 repetições de: (A) isolado sem aquecimento, (B) isolado com aquecimento, (C) misturado sem
aquecimento, (D) misturado com aquecimento, o custo da 1ª chamada (canal frio × quente) e o efeito do intervalo ocioso
entre chamadas (com REST como controle).

## 10. Ameaças à validade

* Ambiente único (Windows + Docker Desktop/WSL2): há sobrecarga da camada de virtualização e do *port-forwarding*.
* Cada cenário foi executado **uma vez** (amostra determinística de 300 requisições por tecnologia); exceto o experimento
  do gRPC (10 repetições), não há intervalos de confiança entre execuções independentes. O desvio-padrão e os percentis
  intra-execução estão disponíveis.
* Gerador de carga em Python (GIL) no mesmo host dos contêineres.
* Perda e atraso apenas no caminho de resposta (ver seção 2); operações não equivalentes em alguns serviços (seção 5).
* Resultados valem para as implementações Python (FastAPI, Spyne, grpcio, websockets) usadas; outras linguagens e
  *runtimes* podem alterar a ordem entre tecnologias.

## 11. Como reproduzir

```powershell
cd root
.\.venv\Scripts\python.exe run_all_scenarios.py          # tudo, sem interação (≈ 2 a 3 h)
.\.venv\Scripts\python.exe run_all_scenarios.py --resume <RUN_ID>   # retoma se for interrompido
.\.venv\Scripts\python.exe run_all_scenarios.py --quick  # versão curta para testar o pipeline
```
Resultados brutos: `tests/results/final/<RUN_ID>/`; material gerado: `docs/material_final/`.
