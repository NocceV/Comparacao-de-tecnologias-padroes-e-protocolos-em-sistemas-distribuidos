import grpc
import pytest
import requests
import time
import protos.message_pb2 as message_pb2
import protos.message_pb2_grpc as message_pb2_grpc

# Endpoints e portas do serviço
GRPC_SERVER_ADDR = "localhost:50054"
METRICS_URL = "http://localhost:50053"

@pytest.fixture(scope="session")
def grpc_stub():
    """Cria o canal e stub para comunicação gRPC com o MessageService."""
    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = message_pb2_grpc.MessageServiceStub(channel)
    # Aguarda o servidor iniciar
    for _ in range(10):
        try:
            grpc.channel_ready_future(channel).result(timeout=2)
            print("✅ gRPC MessageService conectado com sucesso!")
            return stub
        except grpc.FutureTimeoutError:
            print("⏳ Aguardando servidor gRPC iniciar...")
            time.sleep(2)
    pytest.fail("❌ Servidor gRPC (MessageService) não disponível após várias tentativas.")


def test_send_message_response(grpc_stub):
    """Testa o envio de uma mensagem via gRPC e valida o retorno."""
    request = message_pb2.SendMessageRequest(
        id=1,
        sender="Vitor",
        content="Mensagem teste via gRPC"
    )
    response = grpc_stub.SendMessage(request)
    assert response.id == 1
    assert response.sender == "Vitor"
    assert "Mensagem teste" in response.content
    assert "T" in response.timestamp  # formato ISO8601
    print(f"📡 Resposta gRPC recebida: {response}")


def test_multiple_requests_latency(grpc_stub):
    """Executa múltiplas chamadas gRPC para medir latência e estabilidade."""
    start = time.time()
    for i in range(5):
        req = message_pb2.SendMessageRequest(id=i, sender="User", content=f"Msg {i}")
        resp = grpc_stub.SendMessage(req)
        assert resp.sender == "User"
    elapsed = time.time() - start
    print(f"⏱️ 5 requisições gRPC executadas em {elapsed:.3f}s")
    assert elapsed < 5.0  # tempo aceitável total


def test_metrics_exposed():
    """Verifica se o endpoint de métricas Prometheus está respondendo corretamente."""
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
