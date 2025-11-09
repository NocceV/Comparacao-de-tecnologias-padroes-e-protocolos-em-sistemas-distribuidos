import grpc
import time
import statistics
import protos.message_pb2 as message_pb2
import protos.message_pb2_grpc as message_pb2_grpc

# Configurações
GRPC_SERVER_ADDR = "localhost:50054"
TOTAL_REQUESTS = 500

def run_stress_test():
    print("=== TESTE DE STRESS - MESSAGE GRPC ===")

    # Cria o canal e stub
    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = message_pb2_grpc.MessageServiceStub(channel)

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        request = message_pb2.SendMessageRequest(
            id=i,
            sender=f"User{i}",
            content=f"Mensagem número {i}"
        )

        start = time.perf_counter()
        try:
            response = stub.SendMessage(request)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            print(f"Mensagem {i} enviada - Status: OK - Tempo: {elapsed:.0f}ms")
        except grpc.RpcError as e:
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            print(f"Mensagem {i} falhou - Status: ERRO ({e.code()}) - Tempo: {elapsed:.0f}ms")

    total_time = (time.perf_counter() - start_total) * 1000
    avg_latency = statistics.mean(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (MESSAGE GRPC) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_latency:.0f}ms")
    print(f"Menor tempo de resposta: {min_latency:.0f}ms")
    print(f"Maior tempo de resposta: {max_latency:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")

if __name__ == "__main__":
    run_stress_test()
