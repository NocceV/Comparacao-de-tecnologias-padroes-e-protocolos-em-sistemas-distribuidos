import grpc
import pytest
import requests
import time
import protos.user_pb2 as user_pb2
import protos.user_pb2_grpc as user_pb2_grpc

# Endpoints de serviço
GRPC_SERVER_ADDR = "localhost:50051"
METRICS_URL = "http://localhost:50052"

@pytest.fixture(scope="session")
def grpc_stub():
    """Cria o canal e stub para comunicação gRPC."""
    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = user_pb2_grpc.UserServiceStub(channel)
    # Aguarda até que o servidor esteja disponível
    for _ in range(10):
        try:
            grpc.channel_ready_future(channel).result(timeout=2)
            print("✅ gRPC UserService conectado com sucesso!")
            return stub
        except grpc.FutureTimeoutError:
            print("⏳ Aguardando servidor gRPC iniciar...")
            time.sleep(2)
    pytest.fail("❌ Servidor gRPC não disponível após várias tentativas.")


def test_get_user_response(grpc_stub):
    """Testa a chamada gRPC GetUser e valida o retorno."""
    request = user_pb2.GetUserRequest(id=1)
    response = grpc_stub.GetUser(request)
    assert response.id == 1
    assert response.name == "User1"
    assert response.email == "user@example.com"
    print(f"📡 Resposta gRPC recebida: {response}")


def test_multiple_requests_latency(grpc_stub):
    """Executa múltiplas chamadas gRPC para medir latência e estabilidade."""
    start = time.time()
    for i in range(5):
        resp = grpc_stub.GetUser(user_pb2.GetUserRequest(id=i))
        assert resp.name.startswith("User")
    elapsed = time.time() - start
    print(f"⏱️ 5 requisições gRPC executadas em {elapsed:.3f}s")


def test_metrics_exposed():
    """Verifica se o endpoint de métricas Prometheus está respondendo."""
    for _ in range(10):
        try:
            r = requests.get(METRICS_URL)
            if r.status_code == 200:
                content = r.text
                assert "grpc_requests_total" in content
                assert "grpc_request_latency_seconds" in content
                print("📊 Métricas gRPC expostas com sucesso!")
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    pytest.fail("❌ Métricas Prometheus não disponíveis em tempo hábil.")
