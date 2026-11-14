import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_delivery import prepare_webhook, webhook_delivery

BASE_URL = "http://localhost:8004"
TOTAL_REQUESTS = 500
RUN_ID = int(time.time())

def register_webhook():
    prepare_webhook("message", f"{BASE_URL}/hooks/messages")


def send_message(index):
    message_data = {
        "sender": f"User{index}",
        "content": f"bench-{RUN_ID}-{index}"
    }
    token = f"bench-{RUN_ID}-{index}"
    elapsed, ok = webhook_delivery("message", f"{BASE_URL}/hooks/messages", f"{BASE_URL}/messages", message_data, token)
    print(f"Mensagem {index} enviada - Status: {'OK' if ok else 'ERRO'} - Tempo: {elapsed:.0f}ms")
    if not ok:
        raise RuntimeError("Callback de mensagem não recebido")
    return elapsed


def main():
    print("=== TESTE DE STRESS - MESSAGE WEBHOOK ===")
    register_webhook()

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        latencies.append(send_message(i))

    total_time = (time.perf_counter() - start_total) * 1000  # ms
    avg_time = statistics.mean(latencies)
    min_time = min(latencies)
    max_time = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (MESSAGE WEBHOOK) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
