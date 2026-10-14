import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_delivery import prepare_webhook, webhook_delivery

BASE_URL = "http://localhost:8023"  # Porta padrão do Event Webhook
TOTAL_REQUESTS = 500
RUN_ID = int(time.time())


def send_event(index):
    """Envia um evento via webhook e mede o tempo de resposta."""
    token = f"bench-{RUN_ID}-{index}"
    event_data = {
        "id": index,
        "type": "PUBLISH",
        "source": token,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    elapsed, ok = webhook_delivery("event", f"{BASE_URL}/hooks/events", f"{BASE_URL}/events", event_data, token)
    print(f"Evento {index} enviado - Status: {'OK' if ok else 'ERRO'} - Tempo: {elapsed:.0f}ms")
    if not ok:
        raise RuntimeError("Callback de evento não recebido")

    return elapsed


def main():
    print("=== TESTE DE STRESS - EVENT WEBHOOK ===")
    prepare_webhook("event", f"{BASE_URL}/hooks/events")

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        latencies.append(send_event(i))

    total_time = (time.perf_counter() - start_total) * 1000  # ms
    avg_time = statistics.mean(latencies)
    min_time = min(latencies)
    max_time = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (EVENT WEBHOOK) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
