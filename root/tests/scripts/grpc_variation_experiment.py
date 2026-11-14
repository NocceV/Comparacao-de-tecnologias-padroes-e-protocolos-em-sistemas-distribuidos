"""
Experimento controlado: por que a latência média do gRPC sobe no tráfego misturado?

Hipótese testada
----------------
No regime determinístico o gRPC executa 100 chamadas consecutivas por serviço
reutilizando o canal HTTP/2 já aberto; o custo da PRIMEIRA chamada (criação
preguiçosa do canal, handshake TCP + HTTP/2, resolução de endereço) é diluído em
100 amostras. No regime estocástico existem apenas 10 chamadas gRPC por serviço
(30 no total, intercaladas com outros protocolos); a mesma chamada "fria" passa a
pesar 1/10 da amostra por serviço. Além disso, o intervalo entre chamadas gRPC
consecutivas aumenta (outros protocolos são executados no meio).

O script mede, na rede IDEAL e com R repetições:
  E : latência da 1ª chamada (canal frio) x 2ª chamada (canal quente) por serviço
  A : isolado, SEM aquecimento (condição "legada")      - 3 x 100 chamadas
  B : isolado, COM aquecimento                          - 3 x 100 chamadas
  C : misturado (7 protocolos, 210 req.), SEM aquecimento - 30 chamadas gRPC
  D : misturado, COM aquecimento                         - 30 chamadas gRPC
e compara as médias, decompondo a diferença entre C e A.
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import time
from datetime import datetime

import lab_utils as lab
import multiprotocol_random_stress_test as mp
from final_benchmark import _call

STUB_ATTRS = ["_grpc_user_stub", "_grpc_msg_stub", "_grpc_evt_stub"]


def reset_stubs():
    for a in STUB_ATTRS:
        setattr(mp, a, None)


def grpc_call(svc, i):
    return _call(svc, "grpc", i)


def isolated(n_per_service: int, warm: bool) -> list:
    reset_stubs()
    lats = []
    for svc in lab.SERVICES:
        if warm:
            for j in range(3):
                grpc_call(svc, 900_000 + j)
        for i in range(1, n_per_service + 1):
            el, ok, _ = grpc_call(svc, i)
            if ok:
                lats.append(el)
    return lats


def mixed(k: int, warm: bool, seed: int) -> list:
    reset_stubs()
    combos = [(s, p) for s in lab.SERVICES for p in lab.PROTOCOLS if p in mp.REGISTRY[s]]
    if warm:
        for s, p in combos:
            for j in range(3):
                _call(s, p, 900_000 + j)
    plan = [(s, p) for (s, p) in combos for _ in range(k)]
    random.Random(seed).shuffle(plan)
    lats = []
    for i, (s, p) in enumerate(plan, 1):
        el, ok, _ = _call(s, p, i)
        if p == "grpc" and ok:
            lats.append(el)
    return lats


def cond_stats(runs: list) -> dict:
    means = [statistics.fmean(r) for r in runs if r]
    pooled = [x for r in runs for x in r]
    return {
        "runs": len(means),
        "samples_per_run": [len(r) for r in runs][:1],
        "mean_of_run_means_ms": round(statistics.fmean(means), 3),
        "stdev_between_runs_ms": round(statistics.stdev(means), 3) if len(means) > 1 else 0.0,
        "median_ms": round(statistics.median(pooled), 3),
        "p95_ms": round(lab.percentile(pooled, 95), 3),
        "max_ms": round(max(pooled), 3),
        "min_ms": round(min(pooled), 3),
    }


GAPS_MS = [0, 5, 20, 50, 100, 250]


def gap_sweep(proto: str, calls_per_service: int) -> dict:
    """Canal/cliente AQUECIDO; varia o intervalo ocioso entre chamadas consecutivas.

    No tráfego misturado, entre duas chamadas gRPC consecutivas o cliente executa
    ~6 chamadas de outros protocolos (dezenas de ms). Este experimento isola o
    efeito do tempo ocioso do canal sobre a latência da chamada seguinte.
    """
    out = {}
    reset_stubs()
    for s in lab.SERVICES:
        for j in range(5):
            _call(s, proto, 900_000 + j)
    for gap in GAPS_MS:
        lats = []
        for s in lab.SERVICES:
            for i in range(1, calls_per_service + 1):
                if gap:
                    time.sleep(gap / 1000.0)
                el, ok, _ = _call(s, proto, 100 * gap + i)
                if ok:
                    lats.append(el)
        out[str(gap)] = {
            "samples": len(lats),
            "mean_ms": round(statistics.fmean(lats), 3),
            "median_ms": round(statistics.median(lats), 3),
            "p95_ms": round(lab.percentile(lats, 95), 3),
            "max_ms": round(max(lats), 3),
            "share_over_10ms_pct": round(100.0 * sum(1 for x in lats if x > 10) / len(lats), 2),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repetitions", type=int, default=10)
    ap.add_argument("--gap-calls", type=int, default=60, help="chamadas por serviço em cada intervalo do gap sweep")
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    R = a.repetitions
    mp.RUN_ID = int(time.time() * 1000)

    # E: primeira vs. segunda chamada
    first, second = {s: [] for s in lab.SERVICES}, {s: [] for s in lab.SERVICES}
    for _ in range(R):
        for s in lab.SERVICES:
            reset_stubs()
            e1, ok1, _ = grpc_call(s, 1)
            e2, ok2, _ = grpc_call(s, 2)
            if ok1 and ok2:
                first[s].append(e1)
                second[s].append(e2)
    cold_vs_warm = {s: {"first_call_mean_ms": round(statistics.fmean(first[s]), 3),
                        "second_call_mean_ms": round(statistics.fmean(second[s]), 3),
                        "first_call_median_ms": round(statistics.median(first[s]), 3),
                        "excess_cold_ms": round(statistics.fmean(first[s]) - statistics.fmean(second[s]), 3)}
                    for s in lab.SERVICES if first[s]}
    excess = statistics.fmean(v["excess_cold_ms"] for v in cold_vs_warm.values())

    A = [isolated(100, False) for _ in range(R)]
    B = [isolated(100, True) for _ in range(R)]
    C = [mixed(10, False, 100 + i) for i in range(R)]
    D = [mixed(10, True, 100 + i) for i in range(R)]

    res = {"timestamp": datetime.now().isoformat(), "repetitions": R,
           "cold_vs_warm_first_call": cold_vs_warm,
           "mean_cold_excess_ms": round(excess, 3),
           "A_isolado_sem_aquecimento": cond_stats(A), "B_isolado_com_aquecimento": cond_stats(B),
           "C_misturado_sem_aquecimento": cond_stats(C), "D_misturado_com_aquecimento": cond_stats(D)}
    a_m = res["A_isolado_sem_aquecimento"]["mean_of_run_means_ms"]
    c_m = res["C_misturado_sem_aquecimento"]["mean_of_run_means_ms"]
    d_m = res["D_misturado_com_aquecimento"]["mean_of_run_means_ms"]
    b_m = res["B_isolado_com_aquecimento"]["mean_of_run_means_ms"]
    res["decomposicao"] = {
        "diferenca_misturado_vs_isolado_sem_aquecimento_ms": round(c_m - a_m, 3),
        "diferenca_misturado_vs_isolado_com_aquecimento_ms": round(d_m - b_m, 3),
        # contribuição teórica da 1ª chamada fria: 3 serviços x excesso / nº de amostras gRPC
        "contribuicao_teorica_cold_isolado_ms": round(3 * excess / 300, 3),
        "contribuicao_teorica_cold_misturado_ms": round(3 * excess / 30, 3),
        "reducao_da_diferenca_pelo_aquecimento_ms": round((c_m - a_m) - (d_m - b_m), 3),
    }
    # F: efeito do intervalo ocioso entre chamadas (gRPC) com controle REST
    res["F_gap_sweep_grpc"] = gap_sweep("grpc", a.gap_calls)
    res["F_gap_sweep_rest_controle"] = gap_sweep("rest", a.gap_calls)
    res["gap_sweep_params"] = {"gaps_ms": GAPS_MS, "calls_per_service": a.gap_calls}
    lab.save_json(os.path.join(a.outdir, "grpc_variation.json"), res)
    for g in GAPS_MS:
        v = res["F_gap_sweep_grpc"][str(g)]
        print(f"gap {g:>3} ms: gRPC mean={v['mean_ms']} median={v['median_ms']} p95={v['p95_ms']} >10ms={v['share_over_10ms_pct']}%")
    print("gRPC variação:", res["decomposicao"])
    for k in ("A_isolado_sem_aquecimento", "B_isolado_com_aquecimento",
              "C_misturado_sem_aquecimento", "D_misturado_com_aquecimento"):
        print(k, res[k]["mean_of_run_means_ms"], "+-", res[k]["stdev_between_runs_ms"], "ms")


if __name__ == "__main__":
    main()
