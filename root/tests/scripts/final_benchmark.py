"""
Bateria final de latência/vazão: regimes DETERMINÍSTICO e ESTOCÁSTICO.

Reutiliza os 21 manipuladores (serviço x protocolo) definidos em
`multiprotocol_random_stress_test.py`, garantindo que as mesmas operações
sejam executadas nos dois regimes e em todos os cenários.

Regras de rigor estatístico
---------------------------
* Mesmo número de requisições para TODAS as tecnologias:
    - determinístico: N requisições por (serviço, protocolo) -> 3N por tecnologia;
    - estocástico   : k requisições por (serviço, protocolo) -> 3k por tecnologia,
                      ordem embaralhada com semente fixa (reprodutível).
* Fase de aquecimento (warm-up) NÃO cronometrada, idêntica para todos
  (W chamadas por combinação), para que a criação preguiçosa de canais/conexões
  (ex.: canal gRPC) não contamine a média das primeiras requisições.
* Latência estatística calculada apenas sobre requisições bem-sucedidas; as
  falhas são contadas separadamente (taxa de sucesso por tecnologia).
* Estatísticas: média, mediana, desvio-padrão amostral, p95, p99, mín, máx.
* Todas as latências brutas são gravadas no JSON para auditoria.
* Consolidação por tecnologia usa amostra agrupada (pooled): média sobre todas
  as amostras e vazão = soma das requisições / soma dos tempos.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import random
import sys
import time
from datetime import datetime

import lab_utils as lab
import multiprotocol_random_stress_test as mp

WARMUP_IDX_BASE = 900_000


def _fresh_run_id() -> None:
    # Garante e-mails/identificadores únicos a cada fase (evita colisões de cadastro)
    mp.RUN_ID = int(time.time() * 1000)


def _call(svc: str, proto: str, idx: int):
    """Executa uma chamada; devolve (latência_ms, ok, tipo_de_falha)."""
    handler = mp.REGISTRY[svc][proto]
    try:
        elapsed, ok = handler(idx)
        return elapsed, bool(ok), (None if ok else "resposta_invalida_ou_rpc_error")
    except Exception as exc:  # timeout, conexão recusada/resetada, etc.
        return 0.0, False, type(exc).__name__


def warmup(combos, n: int) -> int:
    if len(combos) <= 1:
        done = 0
        for svc, proto in combos:
            for j in range(n):
                _call(svc, proto, WARMUP_IDX_BASE + j)
                done += 1
        return done

    def _w(combo):
        svc, proto = combo
        for j in range(n):
            _call(svc, proto, WARMUP_IDX_BASE + j)
        return n

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(combos), 21)) as ex:
        return sum(ex.map(_w, combos))


def _kinds(results):
    out = {}
    for r in results:
        if not r["ok"]:
            out[r["error"]] = out.get(r["error"], 0) + 1
    return out


def run_deterministic(n: int, warm: int, outdir: str, scenario: str) -> dict:
    protocols = [p for p in lab.PROTOCOLS]
    report = {"regime": "deterministico", "scenario": scenario, "requests_per_combination": n,
              "warmup_per_combination": warm, "timestamp": datetime.now().isoformat(),
              "combinations": {}, "per_protocol": {}}
    pooled = {p: {"lat": [], "total": 0, "wall": 0.0, "errors": {}} for p in protocols}
    _fresh_run_id()

    def _run_combo(svc: str, proto: str):
        w = warmup([(svc, proto)], warm)
        results = []
        t0 = time.perf_counter()
        for i in range(1, n + 1):
            el, ok, err = _call(svc, proto, i)
            results.append({"lat": el, "ok": ok, "error": err})
        wall = time.perf_counter() - t0
        lat_ok = [r["lat"] for r in results if r["ok"]]
        stats = lab.summarize(lat_ok, n, wall)
        stats["warmup_requests"] = w
        stats["error_kinds"] = _kinds(results)
        stats["latencies_ms"] = [round(x, 3) for x in lat_ok]
        return svc, proto, stats, lat_ok, wall

    for svc in lab.SERVICES:
        avail = [proto for proto in protocols if proto in mp.REGISTRY[svc]]
        if scenario == "ideal":
            combo_results = [_run_combo(svc, proto) for proto in avail]
        else:
            # Nos cenários com atraso/perda de rede (realista/crítico), cada contêiner
            # gasta >98% do tempo aguardando o RTT/RTO do tc netem em seu próprio namespace.
            # Executar os 7 contêineres do domínio em paralelo preserva a execução
            # estritamente sequencial (1 cliente por contêiner) sem interferência de CPU.
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(avail)) as ex:
                futs = [ex.submit(_run_combo, svc, proto) for proto in avail]
                combo_results = [f.result() for f in futs]

        for svc_, proto, stats, lat_ok, wall in combo_results:
            report["combinations"][f"{svc_}_{proto}"] = stats
            pl = pooled[proto]
            pl["lat"] += lat_ok
            pl["total"] += n
            pl["wall"] += wall
            for k, v in stats["error_kinds"].items():
                pl["errors"][k] = pl["errors"].get(k, 0) + v
            print(f"[{scenario}] DET {svc_:<7} {proto:<9} ok={stats['success']:>3}/{n} "
                  f"avg={stats['avg_latency_ms']} p95={stats['p95_latency_ms']} thr={stats['throughput_rps']} req/s")

    for proto, pl in pooled.items():
        if pl["total"]:
            s = lab.summarize(pl["lat"], pl["total"], pl["wall"])
            s["error_kinds"] = pl["errors"]
            report["per_protocol"][proto] = s
    lab.save_json(os.path.join(outdir, f"deterministic_{scenario}.json"), report)
    return report


def run_stochastic(k: int, warm: int, concurrency: int, seed: int, outdir: str, scenario: str) -> dict:
    combos = [(s, p) for s in lab.SERVICES for p in lab.PROTOCOLS if p in mp.REGISTRY[s]]
    _fresh_run_id()
    w = warmup(combos, warm)
    plan = [(s, p) for (s, p) in combos for _ in range(k)]
    random.Random(seed).shuffle(plan)
    total = len(plan)
    results = []

    def one(item):
        i, (s, p) = item
        el, ok, err = _call(s, p, i)
        return {"order": i, "service": s, "protocol": p, "lat": el, "ok": ok, "error": err}

    t0 = time.perf_counter()
    items = list(enumerate(plan, 1))
    if concurrency <= 1:
        for it in items:
            results.append(one(it))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            results = list(ex.map(one, items))
    wall = time.perf_counter() - t0

    report = {"regime": "estocastico", "scenario": scenario, "total_requests": total,
              "requests_per_combination": k, "requests_per_protocol": total // len(lab.PROTOCOLS),
              "concurrency": concurrency, "shuffle_seed": seed, "warmup_per_combination": warm,
              "warmup_requests_total": w, "timestamp": datetime.now().isoformat(),
              "overall": None, "per_protocol": {}, "per_service": {}}
    ok_all = [r["lat"] for r in results if r["ok"]]
    report["overall"] = lab.summarize(ok_all, total, wall)
    for proto in lab.PROTOCOLS:
        rs = [r for r in results if r["protocol"] == proto]
        if not rs:
            continue
        s = lab.summarize([r["lat"] for r in rs if r["ok"]], len(rs), wall)
        s["percentage_of_load"] = round(100.0 * len(rs) / total, 4)
        s["error_kinds"] = _kinds(rs)
        s["latencies_ms"] = [round(r["lat"], 3) for r in rs if r["ok"]]
        # throughput por protocolo não é definido isoladamente (execução intercalada)
        s.pop("throughput_rps", None)
        s.pop("goodput_rps", None)
        report["per_protocol"][proto] = s
    for svc in lab.SERVICES:
        rs = [r for r in results if r["service"] == svc]
        s = lab.summarize([r["lat"] for r in rs if r["ok"]], len(rs), wall)
        s["percentage_of_load"] = round(100.0 * len(rs) / total, 4)
        s.pop("throughput_rps", None)
        s.pop("goodput_rps", None)
        report["per_service"][svc] = s
    print(f"[{scenario}] STO total={total} conc={concurrency} wall={wall:.2f}s "
          f"thr={report['overall']['throughput_rps']} req/s ok={report['overall']['success']}")
    lab.save_json(os.path.join(outdir, f"stochastic_{scenario}.json"), report)
    return report


def main():
    ap = argparse.ArgumentParser(description="Bateria final determinística/estocástica")
    ap.add_argument("--regime", choices=["deterministic", "stochastic", "both"], default="both")
    ap.add_argument("--scenario", choices=list(lab.SCENARIOS), default="ideal")
    ap.add_argument("--det-requests", type=int, default=100, help="req. por (serviço, protocolo)")
    ap.add_argument("--sto-per-combo", type=int, default=10, help="req. por (serviço, protocolo) no estocástico")
    ap.add_argument("--warmup", type=int, default=3, help="chamadas de aquecimento por combinação")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    sc = lab.SCENARIOS[a.scenario]
    if a.regime in ("deterministic", "both"):
        run_deterministic(a.det_requests, a.warmup, a.outdir, a.scenario)
    if a.regime in ("stochastic", "both"):
        run_stochastic(a.sto_per_combo, a.warmup, sc["stochastic_concurrency"], a.seed, a.outdir, a.scenario)


if __name__ == "__main__":
    main()
