import requests
import time
import pytest

# URL base do serviço GraphQL
GRAPHQL_URL = "http://localhost:8001/graphql"
HEALTH_URL = "http://localhost:8001/health"
METRICS_URL = "http://localhost:8001/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    """Aguarda o serviço subir antes dos testes."""
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço GraphQL disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço GraphQL não iniciou a tempo.")


def test_healthcheck():
    """Verifica se o endpoint /health está ativo."""
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_graphql_query_user():
    """Valida a query GraphQL de usuário."""
    query = """
    query {
        user(id: 1) {
            id
            name
            email
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    user = data["data"]["user"]
    assert user["id"] == 1
    assert user["name"] == "User1"
    assert user["email"] == "user@example.com"


def test_metrics_exposed():
    """Verifica se o endpoint /metrics está expondo as métricas Prometheus."""
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    # Verifica se as métricas principais estão sendo expostas
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content


def test_graphql_multiple_requests():
    """Simula múltiplas requisições GraphQL para medir estabilidade."""
    query = """
    query {
        user(id: 5) {
            id
            name
            email
        }
    }
    """
    for i in range(20):
        resp = requests.post(GRAPHQL_URL, json={"query": query})
        assert resp.status_code == 200
        assert "data" in resp.json()
        print(f"Requisição {i+1} OK")


def test_performance_latency():
    """Mede tempo médio de resposta do endpoint GraphQL."""
    query = """
    query {
        user(id: 10) {
            id
            name
            email
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
    print(f"⏱️ Latência média: {avg_latency:.4f}s")
    assert avg_latency < 1.0  # tempo esperado (ajuste conforme ambiente)
