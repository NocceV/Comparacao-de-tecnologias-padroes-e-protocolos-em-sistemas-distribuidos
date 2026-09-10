import argparse
import asyncio
import concurrent.futures
import json
import os
import random
import statistics
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import requests

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    import grpc
    import user.protos.user_pb2 as user_pb2
    import user.protos.user_pb2_grpc as user_pb2_grpc
    HAS_GRPC_USER = True
except (ImportError, ModuleNotFoundError):
    HAS_GRPC_USER = False

RUN_ID = int(time.time())

# Definição das chamadas por Serviço x Protocolo
def call_user_rest(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8002/user/create", params={"name": f"U{idx}", "email": f"rnd_u_{RUN_ID}_{idx}@test.com"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_user_graphql(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8001/graphql", json={"query": f"query {{ user(id: {idx}) {{ id name email }} }}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200 and "errors" not in r.json()

def call_user_soap(idx: int) -> Tuple[float, bool]:
    body = f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><CreateUser><name>U{idx}</name><email>rnd_soap_{RUN_ID}_{idx}@test.com</email></CreateUser></soap:Body></soap:Envelope>"""
    start = time.perf_counter()
    r = requests.post("http://localhost:8006/soap/users", data=body, headers={"Content-Type": "text/xml"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_user_webhook(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8003/users", json={"name": f"U{idx}", "email": f"rnd_wh_{RUN_ID}_{idx}@test.com"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_user_sse(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8007/user/create", params={"name": f"U{idx}", "email": f"rnd_sse_{RUN_ID}_{idx}@test.com"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_user_websocket(idx: int) -> Tuple[float, bool]:
    if not HAS_WEBSOCKETS:
        return 0.0, False
    async def _send():
        async with websockets.connect("ws://localhost:8005/ws/users", close_timeout=2) as ws:
            s = time.perf_counter()
            await ws.send(json.dumps({"action": "create_user", "data": {"name": f"U{idx}", "email": f"rnd_ws_{RUN_ID}_{idx}@test.com"}}))
            m = json.loads(await ws.recv())
            return (time.perf_counter() - s) * 1000, m.get("event") == "user_created"
    return asyncio.run(_send())

# Message
def call_message_rest(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8012/messages/create", json={"user": f"U{idx}", "content": f"Msg {RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_message_graphql(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8011/graphql", json={"query": f"query {{ message(id: {idx}) {{ id user content }} }}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200 and "errors" not in r.json()

def call_message_soap(idx: int) -> Tuple[float, bool]:
    body = f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><CreateMessage><user>U{idx}</user><content>SOAP {RUN_ID}_{idx}</content></CreateMessage></soap:Body></soap:Envelope>"""
    start = time.perf_counter()
    r = requests.post("http://localhost:8016/soap/messages", data=body, headers={"Content-Type": "text/xml"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_message_webhook(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8004/messages", json={"sender": f"U{idx}", "content": f"Hook {RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_message_sse(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8017/messages/create", json={"user": f"U{idx}", "content": f"SSE {RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_message_websocket(idx: int) -> Tuple[float, bool]:
    if not HAS_WEBSOCKETS:
        return 0.0, False
    async def _send():
        async with websockets.connect("ws://localhost:8015/ws/messages", close_timeout=2) as ws:
            s = time.perf_counter()
            await ws.send(json.dumps({"action": "send_message", "data": {"user": f"U{idx}", "content": f"WS {RUN_ID}_{idx}"}}))
            m = json.loads(await ws.recv())
            return (time.perf_counter() - s) * 1000, m.get("event") == "message_created"
    return asyncio.run(_send())

# Event
def call_event_rest(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8022/create", params={"type": "PUBLISH", "source": f"src_{RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_event_graphql(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8021/graphql", json={"query": f"query {{ event(id: {idx}) {{ id type source }} }}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200 and "errors" not in r.json()

def call_event_soap(idx: int) -> Tuple[float, bool]:
    body = f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><CreateEvent><type>PUBLISH</type><source>src_{RUN_ID}_{idx}</source></CreateEvent></soap:Body></soap:Envelope>"""
    start = time.perf_counter()
    r = requests.post("http://localhost:8026/soap/events", data=body, headers={"Content-Type": "text/xml"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_event_webhook(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8023/events", json={"type": "PUBLISH", "source": f"src_{RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_event_sse(idx: int) -> Tuple[float, bool]:
    start = time.perf_counter()
    r = requests.post("http://localhost:8027/create", params={"type": "PUBLISH", "source": f"src_{RUN_ID}_{idx}"}, timeout=5)
    return (time.perf_counter() - start) * 1000, r.status_code == 200

def call_event_websocket(idx: int) -> Tuple[float, bool]:
    if not HAS_WEBSOCKETS:
        return 0.0, False
    async def _send():
        async with websockets.connect("ws://localhost:8025/ws/events", close_timeout=2) as ws:
            s = time.perf_counter()
            await ws.send(json.dumps({"action": "publish_event", "data": {"type": "publish", "source": f"src_{RUN_ID}_{idx}"}}))
            m = json.loads(await ws.recv())
            return (time.perf_counter() - s) * 1000, m.get("event") == "event_published"
    return asyncio.run(_send())


REGISTRY: Dict[str, Dict[str, Callable[[int], Tuple[float, bool]]]] = {
    "user": {
        "rest": call_user_rest,
        "graphql": call_user_graphql,
        "soap": call_user_soap,
        "webhook": call_user_webhook,
        "sse": call_user_sse,
    },
    "message": {
        "rest": call_message_rest,
        "graphql": call_message_graphql,
        "soap": call_message_soap,
        "webhook": call_message_webhook,
        "sse": call_message_sse,
    },
    "event": {
        "rest": call_event_rest,
        "graphql": call_event_graphql,
        "soap": call_event_soap,
        "webhook": call_event_webhook,
        "sse": call_event_sse,
    },
}

if HAS_WEBSOCKETS:
    REGISTRY["user"]["websocket"] = call_user_websocket
    REGISTRY["message"]["websocket"] = call_message_websocket
    REGISTRY["event"]["websocket"] = call_event_websocket


def run_multiprotocol_test(
    service_filter: str = "all",
    total_requests: int = 500,
    concurrency: int = 1,
    output_file: Optional[str] = None
):
    # Monta lista de pares (serviço, protocolo, handler)
    targets = []
    services_to_test = list(REGISTRY.keys()) if service_filter == "all" else [service_filter]
    for s in services_to_test:
        if s in REGISTRY:
            for p, handler in REGISTRY[s].items():
                targets.append((s, p, handler))

    if not targets:
        print(f"❌ Nenhum alvo encontrado para o serviço '{service_filter}'.")
        return

    print("==========================================================================")
    print("🎲 TESTE DE CARGA MULTI-PROTOCOLO ALEATÓRIO UNIFICADO")
    print("==========================================================================")
    print(f"Serviço alvo: {service_filter.upper()}")
    print(f"Total de requisições: {total_requests}")
    print(f"Concorrência: {concurrency} thread(s)")
    print(f"Alvos disponíveis ({len(targets)} combinações):")
    for s, p, _ in targets:
        print(f"  • {s.upper()} via {p.upper()}")
    print("--------------------------------------------------------------------------")

    proto_stats: Dict[str, Dict] = {}
    service_stats: Dict[str, Dict] = {}

    def execute_one(idx: int) -> Tuple[str, str, float, bool]:
        s, p, handler = random.choice(targets)
        try:
            elapsed, ok = handler(idx)
        except Exception:
            elapsed = 0.0
            ok = False
        return s, p, elapsed, ok

    start_total = time.perf_counter()
    results = []

    if concurrency <= 1:
        for i in range(1, total_requests + 1):
            res = execute_one(i)
            results.append(res)
            s, p, el, ok = res
            status_txt = "OK" if ok else "ERRO"
            print(f"[{i:04d}/{total_requests:04d}] {s.upper():<7} | {p.upper():<9} | {status_txt:<4} | {el:6.1f}ms")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(execute_one, i) for i in range(1, total_requests + 1)]
            for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                res = fut.result()
                results.append(res)
                s, p, el, ok = res
                status_txt = "OK" if ok else "ERRO"
                print(f"[{i:04d}/{total_requests:04d}] {s.upper():<7} | {p.upper():<9} | {status_txt:<4} | {el:6.1f}ms")

    total_time_ms = (time.perf_counter() - start_total) * 1000
    throughput = total_requests / (total_time_ms / 1000) if total_time_ms > 0 else 0

    # Agregar estatísticas
    for s, p, el, ok in results:
        # Por protocolo
        if p not in proto_stats:
            proto_stats[p] = {"count": 0, "success": 0, "errors": 0, "latencies": []}
        proto_stats[p]["count"] += 1
        if ok:
            proto_stats[p]["success"] += 1
            proto_stats[p]["latencies"].append(el)
        else:
            proto_stats[p]["errors"] += 1

        # Por serviço
        if s not in service_stats:
            service_stats[s] = {"count": 0, "success": 0, "errors": 0, "latencies": []}
        service_stats[s]["count"] += 1
        if ok:
            service_stats[s]["success"] += 1
            service_stats[s]["latencies"].append(el)
        else:
            service_stats[s]["errors"] += 1

    # Imprimir tabelas comparativas
    print("\n" + "=" * 80)
    print("📊 1. COMPARATIVO POR PROTOCOLO (DISTRIBUIÇÃO ALEATÓRIA)")
    print("=" * 80)
    print(f"{'PROTOCOLO':<12} | {'REQ':<6} | {'% TOTAL':<8} | {'SUCESSO':<8} | {'ERROS':<6} | {'MÉDIA(ms)':<10} | {'MÍN(ms)':<8} | {'MÁX(ms)':<8}")
    print("-" * 80)

    proto_summary = {}
    for p, st in sorted(proto_stats.items()):
        cnt = st["count"]
        pct = (cnt / total_requests) * 100
        lats = st["latencies"]
        avg_l = statistics.mean(lats) if lats else 0.0
        min_l = min(lats) if lats else 0.0
        max_l = max(lats) if lats else 0.0
        proto_summary[p] = {
            "requests": cnt, "percentage": pct, "success": st["success"], "errors": st["errors"],
            "avg_latency_ms": round(avg_l, 2), "min_latency_ms": round(min_l, 2), "max_latency_ms": round(max_l, 2)
        }
        print(f"{p.upper():<12} | {cnt:<6} | {pct:6.1f}% | {st['success']:<8} | {st['errors']:<6} | {avg_l:10.1f} | {min_l:8.1f} | {max_l:8.1f}")

    print("\n" + "=" * 80)
    print("📊 2. COMPARATIVO POR SERVIÇO")
    print("=" * 80)
    print(f"{'SERVIÇO':<12} | {'REQ':<6} | {'% TOTAL':<8} | {'SUCESSO':<8} | {'ERROS':<6} | {'MÉDIA(ms)':<10}")
    print("-" * 80)
    service_summary = {}
    for s, st in sorted(service_stats.items()):
        cnt = st["count"]
        pct = (cnt / total_requests) * 100
        lats = st["latencies"]
        avg_l = statistics.mean(lats) if lats else 0.0
        service_summary[s] = {"requests": cnt, "percentage": pct, "success": st["success"], "errors": st["errors"], "avg_latency_ms": round(avg_l, 2)}
        print(f"{s.upper():<12} | {cnt:<6} | {pct:6.1f}% | {st['success']:<8} | {st['errors']:<6} | {avg_l:10.1f}")

    print("-" * 80)
    total_succ = sum(st["success"] for st in proto_stats.values())
    total_err = sum(st["errors"] for st in proto_stats.values())
    print(f"Tempo total do teste: {total_time_ms / 1000:.2f}s ({total_time_ms:.0f}ms)")
    print(f"Throughput geral: {throughput:.2f} req/s")
    print(f"Taxa de sucesso global: {(total_succ / total_requests) * 100:.1f}% ({total_succ} sucessos, {total_err} erros)")
    print("=" * 80)

    # Salva em JSON se solicitado ou padrão
    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("../results/raw", exist_ok=True)
        output_file = f"../results/raw/random_stress_{service_filter}_{ts}.json"

    try:
        report = {
            "title": "Teste de Carga Aleatório Multi-Protocolo",
            "service_filter": service_filter,
            "timestamp": datetime.now().isoformat(),
            "total_requests": total_requests,
            "concurrency": concurrency,
            "total_time_ms": total_time_ms,
            "throughput_rps": throughput,
            "protocols": proto_summary,
            "services": service_summary,
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"💾 Relatório JSON completo exportado para: {output_file}")
    except Exception as e:
        print(f"⚠️ Não foi possível salvar JSON em {output_file}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Teste de Carga Multi-Protocolo Aleatório")
    parser.add_argument("--service", choices=["all", "user", "message", "event"], default="all", help="Serviço alvo (padrão: all)")
    parser.add_argument("--requests", type=int, default=500, help="Quantidade de requisições (padrão: 500)")
    parser.add_argument("--concurrency", type=int, default=1, help="Número de threads simultâneas (padrão: 1)")
    parser.add_argument("--output", type=str, default=None, help="Caminho do arquivo JSON para salvar relatório")
    args = parser.parse_args()

    run_multiprotocol_test(
        service_filter=args.service,
        total_requests=args.requests,
        concurrency=args.concurrency,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
