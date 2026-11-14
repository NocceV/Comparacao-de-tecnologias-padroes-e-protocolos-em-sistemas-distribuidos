"""
Teste de RESILIÊNCIA: como cada tecnologia reage quando a conexão falha.

Dois tipos de falha são injetados em um serviço (user-<tecnologia>) enquanto
um cliente envia requisições a taxa constante (10 req/s, timeout 2 s):

  * BLACKOUT : perda de 100 % dos pacotes de resposta por `blackout_s` segundos
               (netem `loss 100%`), depois a rede é restabelecida. A conexão
               TCP/HTTP2 existente sobrevive ou não conforme o protocolo.
  * RESTART  : `docker restart` do contêiner (queda total do serviço e das
               conexões, seguida de reinício do processo).

Comportamento do cliente por tecnologia (política padrão da biblioteca):
  * REST / SOAP / GraphQL / Webhook / SSE : nova conexão HTTP a cada requisição,
        sem retentativa (mesma política dos demais testes).
  * WebSocket : UMA conexão persistente; em caso de erro o cliente descarta a
        conexão e reconecta na próxima tentativa.
  * gRPC      : UM canal persistente; reconexão automática da biblioteca com o
        backoff PADRÃO do gRPC (1 s inicial, x1,6, máx. 120 s).
  * gRPC (backoff ajustado) : mesmo canal persistente, porém com backoff de
        reconexão limitado a 100 ms - 1 s (opções de canal), para mostrar o
        efeito da configuração.

Métricas: falhas, indisponibilidade observada pelo cliente (primeira falha ->
primeiro sucesso seguinte), tempo de recuperação após o fim da falha e latência
da primeira resposta após recuperação.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import threading
import time
import warnings
from datetime import datetime
from types import SimpleNamespace

warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests as _requests

import lab_utils as lab
import multiprotocol_random_stress_test as mp

TIMEOUT_S = 2.0
RATE_HZ = 10.0
DURATION_S = 30.0
FAULT_AT_S = 8.0
BLACKOUT_S = 6.0

# Todas as chamadas HTTP dos manipuladores passam a usar timeout uniforme de 2 s
mp.requests = SimpleNamespace(
    post=lambda *a, **k: _requests.post(*a, **{**k, "timeout": TIMEOUT_S}),
    get=lambda *a, **k: _requests.get(*a, **{**k, "timeout": TIMEOUT_S}),
)

VARIANTS = ["rest", "soap", "graphql", "webhook", "sse", "websocket", "grpc", "grpc_tuned"]
LABEL = {**lab.PROTOCOL_LABEL, "grpc_tuned": "gRPC (backoff ajustado)"}


class HttpClient:
    def __init__(self, proto):
        self.proto = proto
        self.handler = mp.REGISTRY["user"][proto]
        self.i = 0

    def call(self):
        self.i += 1
        el, ok = self.handler(500_000 + self.i)
        if not ok:
            raise RuntimeError("resposta inválida")

    def close(self):
        pass


class WebSocketClient:
    """Conexão persistente com reconexão sob demanda."""

    def __init__(self):
        from websockets.sync.client import connect
        self._connect = connect
        self.ws = None
        self.i = 0

    def call(self):
        self.i += 1
        try:
            if self.ws is None:
                self.ws = self._connect("ws://localhost:8005/ws/users", open_timeout=TIMEOUT_S,
                                        close_timeout=0.5)
            self.ws.send(json.dumps({"action": "create_user", "data": {
                "name": f"R{self.i}", "email": f"res_ws_{time.time_ns()}_{self.i}@t.com"}}))
            msg = json.loads(self.ws.recv(timeout=TIMEOUT_S))
            if msg.get("event") != "user_created":
                raise RuntimeError("resposta inválida")
        except Exception:
            try:
                if self.ws is not None:
                    self.ws.close()
            except Exception:
                pass
            self.ws = None
            raise

    def close(self):
        try:
            if self.ws is not None:
                self.ws.close()
        except Exception:
            pass


class GrpcClient:
    def __init__(self, tuned: bool):
        import grpc
        import user.protos.user_pb2 as pb
        import user.protos.user_pb2_grpc as pbg
        opts = []
        if tuned:
            opts = [("grpc.initial_reconnect_backoff_ms", 100), ("grpc.min_reconnect_backoff_ms", 100),
                    ("grpc.max_reconnect_backoff_ms", 1000)]
        self.channel = grpc.insecure_channel("localhost:50051", options=opts)
        self.stub = pbg.UserServiceStub(self.channel)
        self.pb = pb
        self.i = 0

    def call(self):
        self.i += 1
        self.stub.GetUser(self.pb.GetUserRequest(id=self.i), timeout=TIMEOUT_S)

    def close(self):
        self.channel.close()


def make_client(variant: str):
    if variant == "websocket":
        return WebSocketClient()
    if variant == "grpc":
        return GrpcClient(False)
    if variant == "grpc_tuned":
        return GrpcClient(True)
    return HttpClient(variant)


def container_of(variant: str) -> str:
    return "user-" + ("grpc" if variant.startswith("grpc") else variant)


def run_one(variant: str, fault: str) -> dict:
    cname = container_of(variant)
    client = make_client(variant)
    # aquecimento (não medido): abre conexão/canal
    for _ in range(3):
        try:
            client.call()
        except Exception:
            pass
    attempts = []
    marks = {"fault_start": None, "fault_end": None}

    def inject():
        time.sleep(FAULT_AT_S)
        marks["fault_start"] = time.perf_counter() - t0
        if fault == "blackout":
            lab.netem_apply(cname, 0, 0, 100.0)
            time.sleep(BLACKOUT_S)
            lab.netem_clear(cname)
        else:
            subprocess.run(["docker", "restart", "-t", "1", cname], capture_output=True, timeout=120)
        marks["fault_end"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    th = threading.Thread(target=inject, daemon=True)
    th.start()
    interval = 1.0 / RATE_HZ
    n = 0
    while True:
        now = time.perf_counter() - t0
        if now >= DURATION_S:
            break
        s = time.perf_counter()
        ok, err = True, None
        try:
            client.call()
        except Exception as exc:
            ok, err = False, type(exc).__name__
        el = (time.perf_counter() - s) * 1000.0
        attempts.append({"t": round(s - t0, 3), "ok": ok, "lat_ms": round(el, 2), "error": err})
        n += 1
        nxt = t0 + n * interval
        delay = nxt - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
    th.join(timeout=60)
    client.close()

    fs, fe = marks["fault_start"], marks["fault_end"]
    fe = fe if fe is not None else DURATION_S
    fails = [a for a in attempts if not a["ok"]]
    first_fail = next((a for a in attempts if not a["ok"] and a["t"] >= (fs or 0)), None)
    out = {"variant": variant, "label": LABEL[variant], "fault": fault, "container": cname,
           "attempts": len(attempts), "failures": len(fails),
           "failure_rate_pct": round(100.0 * len(fails) / max(len(attempts), 1), 2),
           "fault_start_s": round(fs, 2) if fs is not None else None, "fault_end_s": round(fe, 2),
           "timeline": attempts}
    if first_fail:
        succ_after = next((a for a in attempts if a["ok"] and a["t"] > first_fail["t"]), None)
        out["first_failure_s"] = first_fail["t"]
        if succ_after:
            out["first_recovery_s"] = succ_after["t"]
            out["outage_observed_s"] = round(succ_after["t"] - first_fail["t"], 3)
            out["recovery_after_fault_end_s"] = round(max(succ_after["t"] - fe, 0.0), 3)
            out["first_response_latency_after_recovery_ms"] = succ_after["lat_ms"]
        else:
            out["outage_observed_s"] = None  # não se recuperou até o fim da janela
            out["recovery_after_fault_end_s"] = None
    else:
        out["outage_observed_s"] = 0.0
        out["recovery_after_fault_end_s"] = 0.0
    ok_lat = [a["lat_ms"] for a in attempts if a["ok"]]
    out["latency_ok"] = lab.summarize(ok_lat, len(attempts), DURATION_S)
    return out


def settle_many(cnames):
    cnames = list(dict.fromkeys(cnames))
    lab.netem_clear_all(cnames)
    lab.wait_all_healthy(180, cnames)
    time.sleep(3)


def _waves_by_disjoint_container(variants):
    waves = []
    remaining = list(variants)
    while remaining:
        wave, used_containers, next_rem = [], set(), []
        for v in remaining:
            c = container_of(v)
            if c not in used_containers:
                wave.append(v)
                used_containers.add(c)
            else:
                next_rem.append(v)
        waves.append(wave)
        remaining = next_rem
    return waves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--faults", default="blackout,restart")
    a = ap.parse_args()
    lab.ensure_sidecar_image()
    report = {"timestamp": datetime.now().isoformat(),
              "params": {"rate_hz": RATE_HZ, "duration_s": DURATION_S, "fault_at_s": FAULT_AT_S,
                         "blackout_s": BLACKOUT_S, "timeout_s": TIMEOUT_S},
              "runs": []}
    vlist = [v for v in a.variants.split(",") if v]
    waves = _waves_by_disjoint_container(vlist)
    for fault in a.faults.split(","):
        by_v = {}
        for wave in waves:
            cnames = [container_of(v) for v in wave]
            settle_many(cnames)
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(wave)) as ex:
                futs = {v: ex.submit(run_one, v, fault) for v in wave}
                for v, f in futs.items():
                    by_v[v] = f.result()
            settle_many(cnames)
        for v in vlist:
            r = by_v[v]
            report["runs"].append(r)
            print(f"[resiliencia] {fault:<8} {r['label']:<24} falhas={r['failures']}/{r['attempts']} "
                  f"indisp={r.get('outage_observed_s')}s rec_pos_falha={r.get('recovery_after_fault_end_s')}s")
    lab.save_json(os.path.join(a.outdir, "resilience.json"), report)


if __name__ == "__main__":
    main()
