import argparse
import asyncio
import json
import random
import statistics
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

import requests

# Imports condicionais para bibliotecas opcionais
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    import grpc
    import protos.user_pb2 as user_pb2
    import protos.user_pb2_grpc as user_pb2_grpc
    HAS_GRPC = True
except (ImportError, ModuleNotFoundError):
    HAS_GRPC = False

RUN_ID = int(time.time())

# Configurações de endpoints
URL_REST = "http://localhost:8002/user/create"
URL_GRAPHQL = "http://localhost:8001/graphql"
URL_SOAP = "http://localhost:8006/soap/users"
URL_WEBHOOK = "http://localhost:8003/users"
URL_WS = "ws://localhost:8005/ws/users"
URL_SSE = "http://localhost:8007/user/create"
GRPC_ADDR = "localhost:50051"

SOAP_HEADERS = {"Content-Type": "text/xml", "SOAPAction": "CreateUser"}


# Handlers por protocolo
def req_rest(index: int) -> tuple[float, bool]:
    params = {"name": f"User{index}", "email": f"user_rnd_rest_{RUN_ID}_{index}@example.com"}
    start = time.perf_counter()
    r = requests.post(URL_REST, params=params, timeout=5)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, r.status_code == 200


def req_graphql(index: int) -> tuple[float, bool]:
    query = f"""query {{ user(id: {index}) {{ id name email }} }}"""
    start = time.perf_counter()
    r = requests.post(URL_GRAPHQL, json={"query": query}, headers={"Content-Type": "application/json"}, timeout=5)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, r.status_code == 200 and "errors" not in r.json()


def req_soap(index: int) -> tuple[float, bool]:
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>User{index}</name>
      <email>user_rnd_soap_{RUN_ID}_{index}@example.com</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>"""
    start = time.perf_counter()
    r = requests.post(URL_SOAP, data=body, headers=SOAP_HEADERS, timeout=5)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, r.status_code == 200


def req_webhook(index: int) -> tuple[float, bool]:
    payload = {"name": f"User{index}", "email": f"user_rnd_hook_{RUN_ID}_{index}@example.com"}
    start = time.perf_counter()
    r = requests.post(URL_WEBHOOK, json=payload, timeout=5)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, r.status_code == 200


def req_sse(index: int) -> tuple[float, bool]:
    params = {"name": f"User{index}", "email": f"user_rnd_sse_{RUN_ID}_{index}@example.com"}
    start = time.perf_counter()
    r = requests.post(URL_SSE, params=params, timeout=5)
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, r.status_code == 200


def req_websocket(index: int) -> tuple[float, bool]:
    if not HAS_WEBSOCKETS:
        return 0.0, False

    async def _send():
        async with websockets.connect(URL_WS, close_timeout=2) as ws:
            payload = {"action": "create_user", "data": {"name": f"User{index}", "email": f"user_rnd_ws_{RUN_ID}_{index}@example.com"}}
            start = time.perf_counter()
            await ws.send(json.dumps(payload))
            msg = json.loads(await ws.recv())
            elapsed = (time.perf_counter() - start) * 1000
            ok = msg.get("event") == "user_created"
            return elapsed, ok

    return asyncio.run(_send())


_grpc_channel = None
_grpc_stub = None

def req_grpc(index: int) -> tuple[float, bool]:
    global _grpc_channel, _grpc_stub
    if not HAS_GRPC:
        return 0.0, False
    if _grpc_stub is None:
        _grpc_channel = grpc.insecure_channel(GRPC_ADDR)
        _grpc_stub = user_pb2_grpc.UserServiceStub(_grpc_channel)

    start = time.perf_counter()
    try:
        req = user_pb2.GetUserRequest(id=index)
        _grpc_stub.GetUser(req, timeout=5)
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, True
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, False


PROTOCOL_HANDLERS: Dict[str, Callable[[int], tuple[float, bool]]] = {
    "rest": req_rest,
    "graphql": req_graphql,
    "soap": req_soap,
    "webhook": req_webhook,
    "sse": req_sse,
}

if HAS_WEBSOCKETS:
    PROTOCOL_HANDLERS["websocket"] = req_websocket

if HAS_GRPC:
    PROTOCOL_HANDLERS["grpc"] = req_grpc


def run_random_stress_test(total_requests: int = 500, selected_protocols: Optional[List[str]] = None, output_file: Optional[str] = None):
    available = [p for p in (selected_protocols or list(PROTOCOL_HANDLERS.keys())) if p in PROTOCOL_HANDLERS]
    if not available:
        print("❌ Nenhum protocolo válido disponível para execução.")
        return

    print("=================================================================")
    print("🎲 TESTE DE STRESS ALEATÓRIO (MULTI-PROTOCOLO) — USER SERVICE")
    print("=================================================================")
    print(f"Total de requisições: {total_requests}")
    print(f"Protocolos ativos: {', '.join(p.upper() for p in available)}")
    print("-----------------------------------------------------------------")

    stats: Dict[str, Dict] = {
        p: {"count": 0, "success": 0, "errors": 0, "latencies": []} for p in available
    }

    start_total = time.perf_counter()

    for i in range(1, total_requests + 1):
        proto = random.choice(available)
        handler = PROTOCOL_HANDLERS[proto]

        try:
            elapsed, ok = handler(i)
        except Exception as exc:
            elapsed = 0.0
            ok = False

        stats[proto]["count"] += 1
        if ok:
            stats[proto]["success"] += 1
            stats[proto]["latencies"].append(elapsed)
        else:
            stats[proto]["errors"] += 1

        status_txt = "OK" if ok else "ERRO"
        print(f"[{i:04d}/{total_requests:04d}] Protocolo: {proto.upper():<10} | Status: {status_txt:<4} | Latência: {elapsed:6.1f}ms")

    total_time_ms = (time.perf_counter() - start_total) * 1000
    overall_throughput = total_requests / (total_time_ms / 1000) if total_time_ms > 0 else 0

    print("\n" + "=" * 80)
    print("📊 RELATÓRIO COMPARATIVO POR PROTOCOLO (ALEATÓRIO)")
    print("=" * 80)
    header = f"{'PROTOCOLO':<12} | {'REQ':<6} | {'% TOTAL':<8} | {'SUCESSO':<8} | {'ERROS':<6} | {'MÉDIA(ms)':<10} | {'MÍN(ms)':<8} | {'MÁX(ms)':<8}"
    print(header)
    print("-" * 80)

    summary_data = {}
    for p in available:
        s = stats[p]
        cnt = s["count"]
        pct = (cnt / total_requests) * 100 if total_requests > 0 else 0
        succ = s["success"]
        err = s["errors"]
        lats = s["latencies"]
        avg_lat = statistics.mean(lats) if lats else 0.0
        min_lat = min(lats) if lats else 0.0
        max_lat = max(lats) if lats else 0.0

        summary_data[p] = {
            "requests": cnt,
            "percentage": pct,
            "success": succ,
            "errors": err,
            "avg_latency_ms": round(avg_lat, 2),
            "min_latency_ms": round(min_lat, 2),
            "max_latency_ms": round(max_lat, 2),
        }

        print(f"{p.upper():<12} | {cnt:<6} | {pct:6.1f}% | {succ:<8} | {err:<6} | {avg_lat:10.1f} | {min_lat:8.1f} | {max_lat:8.1f}")

    print("-" * 80)
    total_succ = sum(s["success"] for s in stats.values())
    total_err = sum(s["errors"] for s in stats.values())
    print(f"Tempo total de execução: {total_time_ms / 1000:.2f}s ({total_time_ms:.0f}ms)")
    print(f"Throughput geral: {overall_throughput:.2f} req/s")
    print(f"Taxa de sucesso global: {(total_succ / total_requests) * 100:.1f}% ({total_succ} sucessos, {total_err} erros)")
    print("=" * 80)

    if output_file:
        out = {
            "service": "user",
            "timestamp": datetime.now().isoformat(),
            "total_requests": total_requests,
            "total_time_ms": total_time_ms,
            "throughput_rps": overall_throughput,
            "protocols": summary_data,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"📁 Resultados salvos em: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Teste de Stress Aleatório Multi-Protocolo (User Service)")
    parser.add_argument("--requests", type=int, default=500, help="Quantidade total de requisições (padrão: 500)")
    parser.add_argument("--protocols", type=str, default="", help="Lista separada por vírgula de protocolos (ex: rest,graphql,sse)")
    parser.add_argument("--output", type=str, default="", help="Caminho do arquivo JSON para salvar os resultados")
    args = parser.parse_args()

    selected = [p.strip().lower() for p in args.protocols.split(",") if p.strip()] if args.protocols else None
    run_random_stress_test(total_requests=args.requests, selected_protocols=selected, output_file=args.output or None)


if __name__ == "__main__":
    main()
