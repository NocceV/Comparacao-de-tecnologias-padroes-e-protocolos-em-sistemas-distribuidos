import requests
import time
import statistics

BASE_URL = "http://localhost:8023"  # Porta padrão do Event Webhook
TOTAL_REQUESTS = 500


def send_event(index):
    """Envia um evento via webhook e mede o tempo de resposta."""
    event_data = {
        "id": index,
        "type": f"event_type_{index}",
        "source": "stress_test",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    start = time.perf_counter()
    response = requests.post(f"{BASE_URL}/events", json=event_data)
    elapsed = (time.perf_counter() - start) * 1000  # ms

    status = response.status_code
    status_text = "OK" if status == 200 else "ERRO"
    print(f"Evento {index} enviado - Status: {status} {status_text} - Tempo: {elapsed:.0f}ms")

    return elapsed


def main():
    print("=== TESTE DE STRESS - EVENT WEBHOOK ===")

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
