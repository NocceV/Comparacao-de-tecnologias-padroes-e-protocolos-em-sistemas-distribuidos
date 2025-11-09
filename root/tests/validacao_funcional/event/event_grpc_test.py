import grpc
import pytest
import requests
import time
import protos.event_pb2 as event_pb2
import protos.event_pb2_grpc as event_pb2_grpc

# Endpoints e portas do serviço
GRPC_SERVER_ADDR = "localhost:50061"
METRICS_URL = "http://localhost:50062"

@pytest.fixture(scope="session")
def grpc_stub():
    """Cria o canal e stub para comunicação gRPC com o EventService."""
    channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
    stub = event_pb2_grpc.EventServiceStub(channel)
    # Aguarda o servidor iniciar
    for _ in range(10):
        try:
            grpc.channel_ready_future(channel).result(timeout=2)
            print("✅ gRPC EventService conectado com sucesso!")
            return stub
        except grpc.FutureTimeoutError:
            print("⏳ Aguardando servidor gRPC iniciar...")
            time.sleep(2)
    pytest.fail("❌ Servidor gRPC (EventService) não disponível após várias tentativas.")


def test_emit_event_response(grpc_stub):
    """Testa o método EmitEvent e valida o retorno."""
    request = event_pb2.Event(
        type="USER_SIGNUP",
        source="auth-service"
    )
    response = grpc_stub.EmitEvent(request)
    assert response.type == "USER_SIGNUP"
    assert response.source == "auth-service"
    assert response.status == "emitted"
    assert "T" in response.timestamp  # formato ISO8601
    print(f"📡 Evento emitido com sucesso: {response}")


def test_stream_events(grpc_stub):
    """Testa o stream de eventos retornado por StreamEvents."""
    request = event_pb2.EventRequest(filter="system")
    stream = grpc_stub.StreamEvents(request)
    first_event = next(stream)  # recebe o primeiro evento
    assert first_event.type == "system_update"
    assert first_event.status == "emitted"
    print(f"🔁 Evento de stream recebido: {first_event}")
    # Fecha o stream
    stream.cancel()


def test_multiple_emit_event_calls(grpc_stub):
    """Executa múltiplas chamadas EmitEvent para medir latência e estabilidade."""
    start = time.time()
    for i in range(5):
        req = event_pb2.Event(type=f"TYPE_{i}", source="batch-tester")
        resp = grpc_stub.EmitEvent(req)
        assert resp.status == "emitted"
    elapsed = time.time() - start
    print(f"⏱️ 5 eventos emitidos via gRPC em {elapsed:.3f}s")
    assert elapsed < 5.0


def test_metrics_exposed():
    """Verifica se o endpoint de métricas Prometheus está respondendo corretamente."""
    for _ in range(10):
        try:
            r = requests.get(METRICS_URL)
            if r.status_code == 200:
                content = r.text
                assert "grpc_requests_total" in content
                assert "grpc_request_latency_seconds" in content
                assert "grpc_events_emitted_total" in content
                print("📊 Métricas Prometheus expostas com sucesso!")
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    pytest.fail("❌ Métricas Prometheus não disponíveis em tempo hábil.")
