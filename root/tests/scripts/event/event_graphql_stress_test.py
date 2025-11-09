import requests
import time
import statistics

GRAPHQL_URL = "http://localhost:8021/graphql"
TOTAL_REQUESTS = 500

def publish_event(index):
    mutation = f"""
    mutation {{
        publishEvent(type: "Teste_{index}", source: "event-graphql") {{
            id
            type
            source
            timestamp
            status
        }}
    }}
    """
    headers = {"Content-Type": "application/json"}
    payload = {"query": mutation}

    start = time.perf_counter()
    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
    elapsed = (time.perf_counter() - start) * 1000  # ms

    status = response.status_code
    status_text = "OK" if status == 200 else "ERRO"
    print(f"Evento {index} publicado - Status: {status} {status_text} - Tempo: {elapsed:.0f}ms")
    return elapsed


def main():
    print("=== TESTE DE STRESS - EVENT GRAPHQL ===")

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        latencies.append(publish_event(i))

    total_time = (time.perf_counter() - start_total) * 1000  # ms
    avg_time = statistics.mean(latencies)
    min_time = min(latencies)
    max_time = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (EVENT GRAPHQL) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
