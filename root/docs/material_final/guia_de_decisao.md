# Guia de Decisão — Qual tecnologia escolher para cada caso?

| Caso de uso | Escolha recomendada | Alternativa | Evitar quando | Evidência experimental (este estudo) |
|---|---|---|---|---|
| Comunicação interna entre microsserviços, alto volume e baixa latência | gRPC | REST | SOAP | Cenário ideal: 0,73 ms de latência média e 1.367 req/s (maior vazão sequencial) |
| Interação bidirecional em tempo real (chat, jogos, painéis operacionais) | WebSocket | SSE (se for só servidor→cliente) | SOAP, Webhook | Cenário ideal: 0,55 ms de latência média (menor entre as 7) |
| Notificações e feeds unidirecionais servidor→cliente (cotações, status, alertas) | SSE | WebSocket | Webhook | Cenário ideal: 6,70 ms / 147 req/s |
| API pública / integração geral entre sistemas heterogêneos | REST | GraphQL | — | Cenário ideal: 6,03 ms / 164 req/s |
| Front-end/mobile com consultas flexíveis (evitar over/underfetching) | GraphQL | REST | — | Cenário ideal: 7,93 ms (1,91 ms acima do REST) |
| Sistemas corporativos legados com contrato formal (WSDL) e WS-* | SOAP | REST | — | Cenário ideal: 5,96 ms / 166 req/s |
| Notificação de eventos a sistemas de terceiros (pagamentos, SaaS) | Webhook | SSE / REST | — | Cenário ideal: 15,83 ms / 63 req/s |
| Rede instável / móvel (alta latência e perda de pacotes) | WebSocket (menor latência) — gRPC (maior taxa de sucesso) | — | Tecnologias que abrem nova conexão a cada requisição, quando a perda é alta | Cenário crítico: WebSocket 506,52 ms; gRPC 100,00% de sucesso |
| Infraestrutura com CPU/RAM restritas (custo de nuvem) | gRPC (menor CPU/req.) e gRPC (menor RAM) | — | Webhook (maior CPU/req.: 10,07 ms) | CPU: gRPC 0,596 ms/req. × Webhook 10,069 ms/req.; RAM pico: gRPC 73 MiB |

> A coluna *Evidência experimental* vem diretamente dos dados desta execução. As recomendações de adequação (colunas 2 a 4) combinam essas evidências com as características de projeto de cada tecnologia discutidas no referencial teórico (paradigma, acoplamento, suporte a navegadores etc.).
