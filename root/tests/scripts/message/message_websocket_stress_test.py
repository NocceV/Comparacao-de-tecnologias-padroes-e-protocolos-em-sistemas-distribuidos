import asyncio
import json
import time
import statistics

import websockets

WS_URL = "ws://localhost:8015/ws/messages"
TOTAL_REQUESTS = 500


async def send_message(socket, index):
    payload = {
        "action": "send_message",
        "data": {"user": f"User{index}", "content": f"Mensagem de teste #{index}"},
    }
    start = time.perf_counter()
    await socket.send(json.dumps(payload))
    response = json.loads(await socket.recv())
    elapsed = (time.perf_counter() - start) * 1000
    status = "OK" if response.get("event") == "message_created" else "ERRO"
    print(f"Mensagem {index} enviada - Status: {status} - Tempo: {elapsed:.0f}ms")
    return elapsed


async def run():
    print("=== TESTE DE STRESS - WEBSOCKET MESSAGE ===")

    async with websockets.connect(WS_URL) as socket:
        latencies = []
        start_total = time.perf_counter()

        for i in range(1, TOTAL_REQUESTS + 1):
            latencies.append(await send_message(socket, i))

        total_time = (time.perf_counter() - start_total) * 1000
        avg_time = statistics.mean(latencies)
        min_time = min(latencies)
        max_time = max(latencies)
        throughput = TOTAL_REQUESTS / (total_time / 1000)

        print("\n=== RESULTADOS - TESTE DE STRESS (WEBSOCKET MESSAGE) ===")
        print(f"Total de requisições: {TOTAL_REQUESTS}")
        print(f"Tempo total do teste: {total_time:.0f}ms")
        print(f"Tempo médio por requisição: {avg_time:.0f}ms")
        print(f"Menor tempo de resposta: {min_time:.0f}ms")
        print(f"Maior tempo de resposta: {max_time:.0f}ms")
        print(f"Requisições por segundo (throughput): {throughput:.2f}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
