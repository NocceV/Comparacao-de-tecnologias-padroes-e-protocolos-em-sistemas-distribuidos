import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List

import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(ROOT_DIR, "tests")
SCRIPTS_DIR = os.path.join(TESTS_DIR, "scripts")
RESULTS_RAW_DIR = os.path.join(TESTS_DIR, "results", "raw")
RESULTS_PROC_DIR = os.path.join(TESTS_DIR, "results", "processed")
SERVICES = ["user", "message", "event"]
PROTOCOLS = ["rest", "soap", "grpc", "websocket", "graphql", "webhook", "sse"]
REQUIRED_TARGETS = {f"{service}-{protocol}" for service in SERVICES for protocol in PROTOCOLS}

# Python interpreter from .venv
VENV_PYTHON = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

SERVICES_HEALTH = {
    # REST
    "user-rest": "http://localhost:8002/health",
    "message-rest": "http://localhost:8012/health",
    "event-rest": "http://localhost:8022/health",
    # GraphQL
    "user-graphql": "http://localhost:8001/health",
    "message-graphql": "http://localhost:8011/health",
    "event-graphql": "http://localhost:8021/health",
    # Webhook
    "user-webhook": "http://localhost:8003/health",
    "message-webhook": "http://localhost:8004/health",
    "event-webhook": "http://localhost:8023/health",
    # WebSocket
    "user-websocket": "http://localhost:8005/health",
    "message-websocket": "http://localhost:8015/health",
    "event-websocket": "http://localhost:8025/health",
    # SOAP
    "user-soap": "http://localhost:8006/health",
    "message-soap": "http://localhost:8016/health",
    "event-soap": "http://localhost:8026/health",
    # SSE
    "user-sse": "http://localhost:8007/health",
    "message-sse": "http://localhost:8017/health",
    "event-sse": "http://localhost:8027/health",
    # Monitoring
    "prometheus": "http://localhost:9090/-/healthy",
}


def check_health(timeout: int = 3) -> Dict[str, bool]:
    print("==========================================================================")
    print("🩺 CHECAGEM DE SAÚDE DOS MICROSSERVIÇOS EXPERIMENTAIS")
    print("==========================================================================")
    status_map = {}
    for name, url in SERVICES_HEALTH.items():
        try:
            r = requests.get(url, timeout=timeout)
            ok = (r.status_code == 200)
            status_map[name] = ok
            symbol = "✅ ONLINE" if ok else f"⚠️ HTTP {r.status_code}"
        except Exception as e:
            status_map[name] = False
            symbol = f"❌ OFFLINE ({type(e).__name__})"
        print(f"  • {name:<20}: {symbol}")

    # gRPC ports check
    import socket
    grpc_targets = [
        ("user-grpc", "localhost", 50051),
        ("message-grpc", "localhost", 50054),
        ("event-grpc", "localhost", 50061),
    ]
    for name, host, port in grpc_targets:
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            status_map[name] = True
            print(f"  • {name:<20}: ✅ ONLINE (Porta {port})")
        except Exception:
            status_map[name] = False
            print(f"  • {name:<20}: ❌ OFFLINE (Porta {port})")

    online = sum(1 for v in status_map.values() if v)
    total = len(status_map)
    print(f"\nTotal online: {online}/{total} serviços.")
    print("==========================================================================\n")
    return status_map


def reset_services():
    compose_file = os.path.join(ROOT_DIR, "infra", "docker-compose.yml")
    subprocess.run(["docker", "compose", "-f", compose_file, "restart"], check=True)
    deadline = time.monotonic() + 60
    while True:
        status = check_health(timeout=1)
        if all(status.get(name, False) for name in REQUIRED_TARGETS):
            return
        if time.monotonic() >= deadline:
            missing = sorted(name for name in REQUIRED_TARGETS if not status.get(name, False))
            raise RuntimeError(f"Serviços indisponíveis após reinício: {', '.join(missing)}")
        time.sleep(2)


def run_deterministic_suite(requests_per_protocol: int = 200, services: List[str] = None):
    print("==========================================================================")
    print("📊 EXECUÇÃO: REGIME DETERMINÍSTICO (ISOLADO POR SERVIÇO E PROTOCOLO)")
    print("==========================================================================")
    if services is None:
        services = SERVICES
    protocols = PROTOCOLS

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(RESULTS_RAW_DIR, exist_ok=True)
    os.makedirs(RESULTS_PROC_DIR, exist_ok=True)

    results = {}
    for svc in services:
        results[svc] = {}
        svc_script = os.path.join(SCRIPTS_DIR, svc, f"{svc}_random_stress_test.py")
        for proto in protocols:
            print(f"\n▶️ Testando {svc.upper()} via {proto.upper()} ({requests_per_protocol} requisições)...")
            out_file = os.path.join(RESULTS_RAW_DIR, f"det_{svc}_{proto}_{ts}.json")
            cmd = [
                VENV_PYTHON,
                svc_script,
                "--requests", str(requests_per_protocol),
                "--protocols", proto,
                "--output", out_file
            ]
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            subprocess.run(cmd, cwd=os.path.join(SCRIPTS_DIR, svc), env=env, check=True)

            if os.path.exists(out_file):
                with open(out_file, "r", encoding="utf-8") as f:
                    results[svc][proto] = json.load(f)

    # Save summary
    summary_path = os.path.join(RESULTS_PROC_DIR, f"deterministic_summary_{ts}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Relatório consolidado determinístico salvo em: {summary_path}")
    return results


def run_stochastic_suite(requests_per_target: int = 200, concurrency: int = 1):
    print("==========================================================================")
    print("🎲 EXECUÇÃO: REGIME ESTOCÁSTICO (MULTI-PROTOCOLO ALEATÓRIO)")
    print("==========================================================================")
    multi_script = os.path.join(SCRIPTS_DIR, "multiprotocol_random_stress_test.py")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(RESULTS_RAW_DIR, f"stochastic_all_{ts}.json")
    os.makedirs(RESULTS_RAW_DIR, exist_ok=True)
    os.makedirs(RESULTS_PROC_DIR, exist_ok=True)

    cmd = [
        VENV_PYTHON,
        multi_script,
        "--service", "all",
        "--requests", str(requests_per_target),
        "--expected-targets", str(len(SERVICES) * len(PROTOCOLS)),
        "--concurrency", str(concurrency),
        "--output", out_file
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(cmd, cwd=SCRIPTS_DIR, env=env, check=True)

    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        proc_file = os.path.join(RESULTS_PROC_DIR, f"stochastic_summary_{ts}.json")
        with open(proc_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Relatório estocástico salvo em: {proc_file}")
        return data
    return None


def collect_prometheus_metrics():
    print("\n🔍 Coletando métricas do Prometheus...")
    collector = os.path.join(SCRIPTS_DIR, "metrics_collector.py")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run([VENV_PYTHON, collector], cwd=SCRIPTS_DIR, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description="Orquestrador de Testes e Benchmark de Sistemas Distribuídos")
    parser.add_argument("--mode", choices=["all", "health", "deterministic", "stochastic", "metrics"], default="all", help="Regime a executar")
    parser.add_argument("--requests", type=int, default=200, help="Quantidade de requisições por combinação serviço/protocolo em ambos os regimes")
    parser.add_argument("--concurrency", type=int, default=1, help="Número de threads simultâneas para o teste estocástico")
    args = parser.parse_args()
    if args.requests <= 0:
        parser.error("--requests deve ser um inteiro positivo")
    if args.concurrency <= 0:
        parser.error("--concurrency deve ser um inteiro positivo")

    status = check_health()
    if args.mode == "health":
        return

    if args.mode in ("all", "deterministic", "stochastic") and not all(status.get(name, False) for name in REQUIRED_TARGETS):
        print("❌ Nem todos os 21 serviços estão online. Inicie o ambiente com 'docker compose up -d' na pasta infra/.")
        sys.exit(1)

    if args.mode in ("all", "deterministic"):
        reset_services()
        run_deterministic_suite(requests_per_protocol=args.requests)

    if args.mode in ("all", "stochastic"):
        reset_services()
        run_stochastic_suite(requests_per_target=args.requests, concurrency=args.concurrency)

    if args.mode in ("all", "metrics"):
        collect_prometheus_metrics()

    print("\n🎉 Bateria de testes concluída com sucesso!")


if __name__ == "__main__":
    main()
