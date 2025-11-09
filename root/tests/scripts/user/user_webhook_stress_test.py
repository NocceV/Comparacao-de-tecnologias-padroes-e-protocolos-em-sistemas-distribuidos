import requests
import time
import statistics
import random

BASE_URL = "http://localhost:8003"
TOTAL_REQUESTS = 500

def register_webhook():
    callback_url = f"{BASE_URL}/webhook/receiver"
    response = requests.post(f"{BASE_URL}/hooks/users", json={"callback_url": callback_url})
    if response.status_code != 200:
        print("❌ Erro ao registrar webhook:", response.text)
    else:
        print("✅ Webhook registrado com sucesso")

def create_user(index):
    user_data = {
        "name": f"User{index}",
        "email": f"user{index}@example.com"
    }
    start = time.perf_counter()
    response = requests.post(f"{BASE_URL}/users", json=user_data)
    elapsed = (time.perf_counter() - start) * 1000  # ms
    status = response.status_code
    print(f"Usuário {index} criado - Status: {status} {'OK' if status == 200 else 'ERRO'} - Tempo: {elapsed:.0f}ms")
    return elapsed

def main():
    print("=== TESTE DE STRESS - WEBHOOK USER ===")
    register_webhook()

    tempos = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        tempos.append(create_user(i))

    total_time = (time.perf_counter() - start_total) * 1000
    avg_time = statistics.mean(tempos)
    min_time = min(tempos)
    max_time = max(tempos)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== TESTE DE STRESS - WEBHOOK USER ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")

if __name__ == "__main__":
    main()
