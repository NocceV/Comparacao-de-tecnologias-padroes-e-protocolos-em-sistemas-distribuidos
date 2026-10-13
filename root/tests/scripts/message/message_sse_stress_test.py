import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_delivery import sse_delivery

BASE_URL = "http://localhost:8017"
TOTAL_REQUESTS = 500
RUN_ID = int(time.time())


def send_message(index):
    token = f"bench-{RUN_ID}-{index}"
    payload = {
        "user": f"User{index}",
        "content": token
    }
    elapsed, ok = sse_delivery(f"{BASE_URL}/sse/messages", f"{BASE_URL}/messages/create", token, json_body=payload)
    print(f"Mensagem {index} enviada via SSE - Status: {'OK' if ok else 'ERRO'} - Tempo: {elapsed:.0f}ms")
    if not ok:
        raise RuntimeError("Evento SSE de mensagem não recebido")
    return elapsed


def main():
    print("=== TESTE DE STRESS - SSE MESSAGE ===")

    tempos = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        tempos.append(send_message(i))

    total_time = (time.perf_counter() - start_total) * 1000
    avg_time = statistics.mean(tempos)
    min_time = min(tempos)
    max_time = max(tempos)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (SSE MESSAGE) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
