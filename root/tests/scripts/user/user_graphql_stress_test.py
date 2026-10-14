import requests
import time
import statistics

GRAPHQL_URL = "http://localhost:8001/graphql"

def run_stress_test(total_requests=500):
    latencies = []
    print("=== TESTE DE STRESS - CRIAR USUÁRIOS ===")

    start_time = time.perf_counter()

    for i in range(total_requests):
        user_id = i + 1
        name = f"User{user_id}"
        email = f"graphql_user_{user_id}@example.com"
        query = "mutation($name: String!, $email: String!) { createUser(name: $name, email: $email) { id name email } }"
        payload = {"query": query, "variables": {"name": name, "email": email}}
        headers = {"Content-Type": "application/json"}

        req_start = time.perf_counter()
        response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
        elapsed = (time.perf_counter() - req_start) * 1000  # ms
        latencies.append(elapsed)

        status = response.status_code
        body = response.json()
        created = (body.get("data") or {}).get("createUser") or {}
        status_text = "OK" if status == 200 and not body.get("errors") and created.get("email") == email else "ERRO"
        print(f"Usuário {user_id} criado - Status: {status} {status_text} - Tempo: {elapsed:.0f}ms")

    total_time = (time.perf_counter() - start_time) * 1000  # ms
    avg_latency = statistics.mean(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    throughput = (total_requests / (total_time / 1000))  # req/s

    print("\n=== TESTE DE STRESS - CRIAR USUÁRIOS ===")
    print(f"Total de requisições: {total_requests}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_latency:.0f}ms")
    print(f"Menor tempo de resposta: {min_latency:.0f}ms")
    print(f"Maior tempo de resposta: {max_latency:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput}")

if __name__ == "__main__":
    run_stress_test()
