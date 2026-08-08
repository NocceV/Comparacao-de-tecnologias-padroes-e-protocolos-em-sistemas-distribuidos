import requests
import json
from datetime import datetime

PROM_URL = "http://localhost:9090/api/v1/query"

# Métricas principais de cada tipo de comunicação
METRICS = [
    'http_requests_total',
    'http_request_duration_seconds_count',
    'grpc_requests_total',
    'grpc_request_latency_seconds_count',
    'ws_connections_total',
    'ws_messages_total',
    'ws_message_duration_seconds_count'
]

# Serviços e protocolos
TARGETS = [
    ("user", "rest"),
    ("user", "graphql"),
    ("user", "grpc"),
    ("user", "webhook"),
    ("user", "websocket"),
    ("message", "rest"),
    ("message", "graphql"),
    ("message", "grpc"),
    ("message", "webhook"),
    ("message", "websocket"),
    ("event", "rest"),
    ("event", "graphql"),
    ("event", "grpc"),
    ("event", "webhook"),
    ("event", "websocket"),
]

def collect_metrics():
    all_data = {}

    for service, proto in TARGETS:
        print(f"🔍 Coletando métricas para {service}-{proto}...")
        data = {}
        for metric in METRICS:
            try:
                # Filtro por label 'job' que você definiu no prometheus.yml
                r = requests.get(PROM_URL, params={'query': f'{metric}{{job="{service}_{proto}"}}'})
                result = r.json().get('data', {}).get('result', [])
                data[metric] = result
            except Exception as e:
                print(f"⚠️ Erro ao coletar {metric} de {service}-{proto}: {e}")
                data[metric] = []
        all_data[f"{service}_{proto}"] = data

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"../results/raw/metrics_{timestamp}.json"
    with open(file_path, "w") as f:
        json.dump(all_data, f, indent=2)
    print(f"✅ Métricas salvas em {file_path}")

if __name__ == "__main__":
    collect_metrics()
