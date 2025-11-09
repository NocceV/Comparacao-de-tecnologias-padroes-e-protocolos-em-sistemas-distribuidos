import requests
import time
import pytest

# URLs do serviço GraphQL (ajuste conforme porta no docker-compose)
GRAPHQL_URL = "http://localhost:8021/graphql"
HEALTH_URL = "http://localhost:8021/health"
METRICS_URL = "http://localhost:8021/metrics"


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    """Aguarda o serviço subir antes dos testes."""
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço event-graphql disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço event-graphql não iniciou a tempo.")


def test_healthcheck():
    """Verifica se o endpoint /health está ativo."""
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_graphql_mutation_publish_event():
    """Valida a mutation GraphQL de publicação de evento."""
    mutation = """
    mutation {
        publishEvent(type: "UserCreated", source: "user-service") {
            id
            type
            source
            timestamp
            status
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": mutation})
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    event = data["data"]["publishEvent"]
    assert event["type"] == "UserCreated"
    assert event["source"] == "user-service"
    assert event["status"] == "published"
    assert event["timestamp"].endswith("Z")
    print(f"📡 Evento publicado com sucesso: {event}")


def test_graphql_query_events_list():
    """Verifica se a lista de eventos contém o evento publicado."""
    query = """
    query {
        events {
            id
            type
            source
            timestamp
            status
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": query})
    assert response.status_code == 200
    data = response.json()
    events = data["data"]["events"]
    assert len(events) >= 1
    print(f"📋 Total de eventos retornados: {len(events)}")


def test_graphql_query_single_event():
    """Busca um evento específico pelo ID."""
    query = """
    query {
        event(id: 1) {
            id
            type
            source
            status
        }
    }
    """
    response = requests.post(GRAPHQL_URL, json={"query": query})
    assert response.status_code == 200
    data = response.json()
    event = data["data"]["event"]
    assert event["id"] == 1
    assert event["status"] == "published"
    print(f"🔍 Evento consultado: {event}")


def test_metrics_exposed():
    """Verifica se o endpoint /metrics está expondo as métricas Prometheus."""
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("✅ Métricas Prometheus expostas corretamente!")


def test_graphql_multiple_requests():
    """Executa várias requisições GraphQL para medir estabilidade."""
    query = """
    query {
        events {
            id
            type
            source
            status
        }
    }
    """
    for i in range(10):
        resp = requests.post(GRAPHQL_URL, json={"query": query})
        assert resp.status_code == 200
        assert "data" in resp.json()
        print(f"📨 Requisição {i+1} OK")


def test_performance_latency():
    """Mede o tempo médio de resposta das queries GraphQL."""
    query = """
    query {
        events {
            id
            type
            status
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
    print(f"⏱️ Latência média (GraphQL Event): {avg_latency:.4f}s")
    assert avg_latency < 1.0
