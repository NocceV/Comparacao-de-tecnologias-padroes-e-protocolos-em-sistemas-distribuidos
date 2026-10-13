import requests
import time
import statistics

GRAPHQL_URL = "http://localhost:8011/graphql"

def run_stress_test(total_requests=500):
    latencies = []
    print("=== TESTE DE STRESS - ENVIAR MENSAGENS ===")

    start_time = time.perf_counter()

    for i in range(total_requests):
        message_id = i + 1
        sender = f"User{message_id}"
        content = f"Msg GraphQL {message_id}"
        query = "mutation($sender: String!, $content: String!) { sendMessage(sender: $sender, content: $content) { id sender content } }"
        payload = {"query": query, "variables": {"sender": sender, "content": content}}
        headers = {"Content-Type": "application/json"}

        req_start = time.perf_counter()
        response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
        elapsed = (time.perf_counter() - req_start) * 1000  # ms
        latencies.append(elapsed)

        status = response.status_code
        body = response.json()
        sent = (body.get("data") or {}).get("sendMessage") or {}
        status_text = "OK" if status == 200 and not body.get("errors") and sent.get("content") == content else "ERRO"
        print(f"Mensagem {message_id} enviada - Status: {status} {status_text} - Tempo: {elapsed:.0f}ms")

    total_time = (time.perf_counter() - start_time) * 1000  # ms
    avg_latency = statistics.mean(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    throughput = total_requests / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (MESSAGE GRAPHQL) ===")
    print(f"Total de requisições: {total_requests}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_latency:.0f}ms")
    print(f"Menor tempo de resposta: {min_latency:.0f}ms")
    print(f"Maior tempo de resposta: {max_latency:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")

if __name__ == "__main__":
    run_stress_test()
