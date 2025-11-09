import grpc
import time
import statistics
import protos.event_pb2 as event_pb2
import protos.event_pb2_grpc as event_pb2_grpc

GRPC_SERVER_ADDR = "localhost:50061"
TOTAL_REQUESTS = 500


def emit_event(stub, index):
    """Envia um evento gRPC e mede o tempo de resposta."""
    request = event_pb2.Event(
        id=index,
        type=f"StressTest_{index}",
        source="event-grpc",
        timestamp="",
        status=""
    )

    start = time.perf_counter()
    response = stub.EmitEvent(request)
    elapsed = (time.perf_counter() - start) * 1000  # ms

    print(f"Evento {index} emitido - Status: 200 OK - Tempo: {elapsed:.0f}ms")
    return elapsed


def main():
    print("=== TESTE DE STRESS - EVENT gRPC ===")

    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = event_pb2_grpc.EventServiceStub(channel)

    # Aguarda o servidor iniciar
    for _ in range(10):
        try:
            grpc.channel_ready_future(channel).result(timeout=2)
            print("✅ Conectado ao EventService gRPC!")
            break
        except grpc.FutureTimeoutError:
            print("⏳ Aguardando servidor gRPC iniciar...")
            time.sleep(2)
    else:
        print("❌ Servidor gRPC não respondeu a tempo.")
        return

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        latencies.append(emit_event(stub, i))

    total_time = (time.perf_counter() - start_total) * 1000  # ms
    avg_time = statistics.mean(latencies)
    min_time = min(latencies)
    max_time = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (EVENT gRPC) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
