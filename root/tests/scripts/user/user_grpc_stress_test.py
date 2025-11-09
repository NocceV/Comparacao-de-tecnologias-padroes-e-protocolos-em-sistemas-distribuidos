import grpc
import time
import statistics
import protos.user_pb2 as user_pb2
import protos.user_pb2_grpc as user_pb2_grpc

# Configurações
GRPC_SERVER_ADDR = "localhost:50051"
TOTAL_REQUESTS = 500

def create_user(stub, index):
    """Envia uma requisição gRPC para obter informações do usuário."""
    request = user_pb2.GetUserRequest(id=index)
    start = time.perf_counter()
    response = stub.GetUser(request)
    elapsed = (time.perf_counter() - start) * 1000  # ms
    print(f"Usuário {index} consultado - Status: OK - Tempo: {elapsed:.0f}ms")
    return elapsed

def main():
    print("=== TESTE DE STRESS - USER GRPC ===")
    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = user_pb2_grpc.UserServiceStub(channel)

    tempos = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        tempos.append(create_user(stub, i))

    total_time = (time.perf_counter() - start_total) * 1000
    avg_time = statistics.mean(tempos)
    min_time = min(tempos)
    max_time = max(tempos)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - USER GRPC ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")

if __name__ == "__main__":
    main()
