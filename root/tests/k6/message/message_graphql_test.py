import requests
import time
import pytest

# URLs do serviço GraphQL (ajuste a porta conforme seu docker-compose)
GRAPHQL_URL = "http://localhost:8011/graphql"
HEALTH_URL = "http://localhost:8011/health"
METRICS_URL = "http://localhost:8011/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    """Aguarda o serviço subir antes dos testes."""
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço message-graphql disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço message-graphql não iniciou a tempo.")


def test_healthcheck():
    """Verifica se o endpoint /health está ativo."""
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_graphql_query_message():
    """Valida a query GraphQL de busca de mensagem."""
    query = """
    query {
        message(id: 1) {
            id
            sender
            content
            timestamp
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    msg = data["data"]["message"]
    assert msg["id"] == 1
    assert msg["sender"] == "User1"
    assert "Mensagem" in msg["content"]
    assert msg["timestamp"].endswith("Z")


def test_graphql_mutation_send_message():
    """Valida a mutation GraphQL de envio de mensagem."""
    mutation = """
    mutation {
        sendMessage(sender: "Vitor", content: "Olá via GraphQL!") {
            id
            sender
            content
            timestamp
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": mutation})
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    msg = data["data"]["sendMessage"]
    assert msg["sender"] == "Vitor"
    assert "Olá via GraphQL" in msg["content"]
    assert msg["timestamp"].endswith("Z")


def test_metrics_exposed():
    """Verifica se o endpoint /metrics está expondo as métricas Prometheus."""
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("✅ Métricas Prometheus expostas corretamente!")


def test_graphql_multiple_requests():
    """Executa várias requisições para medir estabilidade."""
    query = """
    query {
        message(id: 5) {
            id
            sender
            content
            timestamp
        }
    }
    """
    for i in range(15):
        resp = requests.post(GRAPHQL_URL, json={"query": query})
        assert resp.status_code == 200
        assert "data" in resp.json()
        print(f"📨 Requisição {i+1} OK")


def test_performance_latency():
    """Mede o tempo médio de resposta das queries GraphQL."""
    query = """
    query {
        message(id: 10) {
            id
            sender
            content
            timestamp
        }
    }
    """
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        resp = requests.post(GRAPHQL_URL, json={"query": query})
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)
        assert resp.status_code == 200
    avg_latency = sum(latencies) / len(latencies)
    print(f"⏱️ Latência média (GraphQL Message): {avg_latency:.4f}s")
    assert avg_latency < 1.0  # tempo esperado ajustável

