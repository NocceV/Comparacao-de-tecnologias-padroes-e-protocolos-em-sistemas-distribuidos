"""
Utilitários compartilhados da bateria final de experimentos.

Responsabilidades
-----------------
* Catálogo oficial de serviços, protocolos, contêineres e portas.
* Definição dos três cenários de rede/carga (ideal, realista, crítico).
* Emulação de rede (atraso, jitter e perda de pacotes) com `tc netem`,
  aplicada via contêiner auxiliar (sidecar) que compartilha o namespace de
  rede do serviço alvo -- não é necessário alterar as imagens dos serviços.
* Leitura de métricas de CPU/memória diretamente da API do Docker Engine
  (contadores cumulativos de cgroup), sem executar nada dentro dos
  contêineres medidos (zero overhead de medição nos serviços).
* Estatística descritiva padronizada (média, mediana, desvio-padrão, p95, p99).
"""
from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional

import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------
SERVICES: List[str] = ["user", "message", "event"]
PROTOCOLS: List[str] = ["rest", "soap", "grpc", "websocket", "graphql", "webhook", "sse"]
PROTOCOL_LABEL = {
    "rest": "REST", "soap": "SOAP", "grpc": "gRPC", "websocket": "WebSocket",
    "graphql": "GraphQL", "webhook": "Webhook", "sse": "SSE",
}
SERVICE_LABEL = {"user": "User", "message": "Message", "event": "Event"}

# Porta HTTP de health-check de cada (serviço, protocolo)
HEALTH_URL: Dict[str, str] = {
    "user-rest": "http://localhost:8002/health", "message-rest": "http://localhost:8012/health",
    "event-rest": "http://localhost:8022/health",
    "user-graphql": "http://localhost:8001/health", "message-graphql": "http://localhost:8011/health",
    "event-graphql": "http://localhost:8021/health",
    "user-webhook": "http://localhost:8003/health", "message-webhook": "http://localhost:8004/health",
    "event-webhook": "http://localhost:8023/health",
    "user-websocket": "http://localhost:8005/health", "message-websocket": "http://localhost:8015/health",
    "event-websocket": "http://localhost:8025/health",
    "user-soap": "http://localhost:8006/health", "message-soap": "http://localhost:8016/health",
    "event-soap": "http://localhost:8026/health",
    "user-sse": "http://localhost:8007/health", "message-sse": "http://localhost:8017/health",
    "event-sse": "http://localhost:8027/health",
}
GRPC_PORT = {"user-grpc": 50051, "message-grpc": 50054, "event-grpc": 50061}


def container_names(protocol: Optional[str] = None) -> List[str]:
    protos = [protocol] if protocol else PROTOCOLS
    return [f"{s}-{p}" for p in protos for s in SERVICES]


# --------------------------------------------------------------------------
# Cenários (derivados do test_plan.md, escalonados para o ambiente local)
# --------------------------------------------------------------------------
# Atraso/jitter/perda são aplicados na interface de saída (eth0) de cada
# contêiner de serviço, i.e., no caminho de RESPOSTA servidor -> cliente.
# O atraso configurado equivale, portanto, ao acréscimo de RTT.
# delay +/- jitter segue distribuição uniforme do netem:
#   realista: 75 +/- 25 ms  => 50..100 ms     (plano: 50-100 ms)
#   crítico : 350 +/- 150ms => 200..500 ms    (plano: 200-500 ms)
# Perda: ponto médio das faixas do plano (2-3 % e 10-15 %).
SCENARIOS: Dict[str, dict] = {
    "ideal": dict(
        label="Ideal", delay_ms=0, jitter_ms=0, loss_pct=0.0,
        stochastic_concurrency=1, resource_concurrency=8,
        description="Rede local sem degradação (0 % de perda), carga sequencial.",
    ),
    "realista": dict(
        label="Realista", delay_ms=75, jitter_ms=25, loss_pct=2.5,
        stochastic_concurrency=10, resource_concurrency=10,
        description="Atraso 50-100 ms, perda 2,5 %, carga moderada (10 clientes simultâneos).",
    ),
    "critico": dict(
        label="Crítico", delay_ms=350, jitter_ms=150, loss_pct=12.5,
        stochastic_concurrency=50, resource_concurrency=24,
        description="Atraso 200-500 ms, perda 12,5 %, carga alta (50 clientes simultâneos).",
    ),
}

SIDECAR_IMAGE = "tc-sidecar:local"


def sh(cmd: List[str], timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check,
                          encoding="utf-8", errors="replace")


def ensure_sidecar_image() -> None:
    """Constrói (uma única vez) a imagem auxiliar com iproute2 (tc)."""
    r = sh(["docker", "image", "inspect", SIDECAR_IMAGE])
    if r.returncode == 0:
        return
    dockerfile = "FROM alpine:3.20\nRUN apk add --no-cache iproute2\n"
    p = subprocess.run(["docker", "build", "-t", SIDECAR_IMAGE, "-"], input=dockerfile,
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"Falha ao construir {SIDECAR_IMAGE}: {p.stderr[-500:]}")


def _tc(container: str, args: str) -> subprocess.CompletedProcess:
    return sh(["docker", "run", "--rm", "--cap-add", "NET_ADMIN", "--network", f"container:{container}",
               SIDECAR_IMAGE, "sh", "-c", args], timeout=60)


def netem_apply(container: str, delay_ms: float, jitter_ms: float, loss_pct: float) -> bool:
    if delay_ms <= 0 and loss_pct <= 0:
        return netem_clear(container)
    parts = []
    if delay_ms > 0:
        parts.append(f"delay {delay_ms}ms {jitter_ms}ms")
    if loss_pct > 0:
        parts.append(f"loss {loss_pct}%")
    r = _tc(container, f"tc qdisc replace dev eth0 root netem {' '.join(parts)}")
    return r.returncode == 0


def netem_clear(container: str) -> bool:
    r = _tc(container, "tc qdisc del dev eth0 root 2>/dev/null; tc qdisc show dev eth0")
    return r.returncode == 0


def netem_show(container: str) -> str:
    r = _tc(container, "tc qdisc show dev eth0")
    return (r.stdout or r.stderr).strip()


def netem_apply_all(containers: Iterable[str], delay_ms: float, jitter_ms: float, loss_pct: float,
                    workers: int = 8) -> Dict[str, bool]:
    containers = list(containers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(lambda c: netem_apply(c, delay_ms, jitter_ms, loss_pct), containers))
    return dict(zip(containers, res))


def netem_clear_all(containers: Iterable[str], workers: int = 8) -> Dict[str, bool]:
    containers = list(containers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(netem_clear, containers))
    return dict(zip(containers, res))


def apply_scenario_network(name: str, containers: Optional[Iterable[str]] = None) -> Dict[str, bool]:
    sc = SCENARIOS[name]
    containers = list(containers) if containers else container_names()
    return netem_apply_all(containers, sc["delay_ms"], sc["jitter_ms"], sc["loss_pct"])


# --------------------------------------------------------------------------
# Health-check
# --------------------------------------------------------------------------
def _grpc_up(port: int) -> bool:
    import socket
    try:
        s = socket.create_connection(("localhost", port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


def wait_all_healthy(timeout_s: int = 300, containers: Optional[Iterable[str]] = None) -> bool:
    """Aguarda todos os serviços responderem. Usa sempre rede SEM netem
    (chamar antes de aplicar o cenário ou após limpá-lo)."""
    wanted = set(containers) if containers else set(container_names())
    deadline = time.time() + timeout_s
    pending = set(wanted)
    while pending and time.time() < deadline:
        for name in list(pending):
            ok = False
            if name in HEALTH_URL:
                try:
                    ok = requests.get(HEALTH_URL[name], timeout=3).status_code == 200
                except Exception:
                    ok = False
            elif name in GRPC_PORT:
                ok = _grpc_up(GRPC_PORT[name])
            if ok:
                pending.discard(name)
        if pending:
            time.sleep(2)
    return not pending


# --------------------------------------------------------------------------
# Docker Engine API (CPU / memória)
# --------------------------------------------------------------------------
_client = None


def docker_client():
    global _client
    if _client is None:
        import docker  # type: ignore
        _client = docker.from_env(timeout=30)
    return _client


def read_container_stats(name: str) -> dict:
    """Leitura instantânea de contadores cgroup via API do Docker Engine.

    cpu_ns            : tempo de CPU cumulativo consumido pelo contêiner (ns)
    throttled_periods : nº cumulativo de períodos CFS em que houve throttling
    throttled_ns      : tempo cumulativo de throttling (ns)
    mem_bytes         : working set = usage - inactive_file (mesma definição do `docker stats`)
    mem_limit         : limite de memória configurado (bytes)
    """
    s = docker_client().containers.get(name).stats(stream=False, one_shot=True)
    cpu = s.get("cpu_stats", {})
    thr = cpu.get("throttling_data", {}) or {}
    mem = s.get("memory_stats", {}) or {}
    inactive = (mem.get("stats") or {}).get("inactive_file", 0) or 0
    usage = mem.get("usage", 0) or 0
    return {
        "t": time.perf_counter(),
        "cpu_ns": (cpu.get("cpu_usage") or {}).get("total_usage", 0),
        "throttled_periods": thr.get("throttled_periods", 0),
        "throttled_ns": thr.get("throttled_time", 0),
        "mem_bytes": max(usage - inactive, 0),
        "mem_limit": mem.get("limit", 0),
    }


def container_health_report() -> List[dict]:
    """Estado de todos os contêineres (restart count e OOM) para auditoria."""
    out = []
    for name in container_names():
        try:
            st = docker_client().containers.get(name).attrs
            out.append({
                "name": name,
                "status": st["State"]["Status"],
                "oom_killed": st["State"].get("OOMKilled", False),
                "restart_count": st.get("RestartCount", 0),
                "nano_cpus": st["HostConfig"].get("NanoCpus"),
                "memory": st["HostConfig"].get("Memory"),
                "memory_swap": st["HostConfig"].get("MemorySwap"),
                "pids_limit": st["HostConfig"].get("PidsLimit"),
            })
        except Exception as e:  # pragma: no cover
            out.append({"name": name, "error": str(e)})
    return out


# --------------------------------------------------------------------------
# Estatística
# --------------------------------------------------------------------------
def percentile(values: List[float], p: float) -> float:
    """Percentil por interpolação linear (equivalente a numpy.percentile padrão)."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summarize(lat_ok_ms: List[float], n_total: int, wall_s: float) -> dict:
    n_ok = len(lat_ok_ms)
    return {
        "requests": n_total,
        "success": n_ok,
        "errors": n_total - n_ok,
        "success_rate_pct": round(100.0 * n_ok / n_total, 3) if n_total else 0.0,
        "avg_latency_ms": round(statistics.fmean(lat_ok_ms), 3) if lat_ok_ms else None,
        "median_latency_ms": round(statistics.median(lat_ok_ms), 3) if lat_ok_ms else None,
        "stdev_latency_ms": round(statistics.stdev(lat_ok_ms), 3) if len(lat_ok_ms) > 1 else 0.0,
        "p95_latency_ms": round(percentile(lat_ok_ms, 95), 3) if lat_ok_ms else None,
        "p99_latency_ms": round(percentile(lat_ok_ms, 99), 3) if lat_ok_ms else None,
        "min_latency_ms": round(min(lat_ok_ms), 3) if lat_ok_ms else None,
        "max_latency_ms": round(max(lat_ok_ms), 3) if lat_ok_ms else None,
        "wall_time_s": round(wall_s, 4),
        # Vazão total = requisições disparadas / tempo decorrido (inclui falhas)
        "throughput_rps": round(n_total / wall_s, 3) if wall_s > 0 else 0.0,
        # Vazão útil (goodput) = apenas respostas bem-sucedidas / tempo decorrido
        "goodput_rps": round(n_ok / wall_s, 3) if wall_s > 0 else 0.0,
    }


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# Prometheus
# --------------------------------------------------------------------------
PROM_QUERY = "http://localhost:9090/api/v1/query"
PROM_METRICS = [
    "http_requests_total", "grpc_requests_total", "ws_messages_total", "ws_connections_total",
    "sse_events_total", "sse_connections_total",
]


def prometheus_snapshot() -> Dict[str, Dict[str, float]]:
    """Valor atual (somado por job) dos contadores exportados pelos serviços."""
    snap: Dict[str, Dict[str, float]] = {}
    for metric in PROM_METRICS:
        try:
            r = requests.get(PROM_QUERY, params={"query": f"sum by (job) ({metric})"}, timeout=10)
            for item in r.json().get("data", {}).get("result", []):
                job = item["metric"].get("job", "?")
                snap.setdefault(job, {})[metric] = float(item["value"][1])
        except Exception:
            continue
    return snap
