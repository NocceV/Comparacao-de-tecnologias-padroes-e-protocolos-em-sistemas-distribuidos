"""
Medição de CONSUMO DE CPU E MEMÓRIA por tecnologia.

Método
------
Para cada tecnologia (REST, SOAP, gRPC, WebSocket, GraphQL, Webhook, SSE):

 1. Aquecimento (não medido) nos 3 serviços da tecnologia.
 2. Janela OCIOSA de `idle_s` segundos (sem carga) -> taxa de CPU ociosa
    (inclui o scraping do Prometheus a cada 5 s) e memória em repouso.
 3. Janela de CARGA: 3 x R requisições (R por serviço, ordem embaralhada com
    semente fixa) com `concurrency` clientes simultâneos. Idêntica para todas
    as tecnologias.
 4. Leitura dos contadores cumulativos de cgroup (via API do Docker Engine,
    sem executar processos dentro dos contêineres medidos):
      * tempo de CPU = Δ cpu_usage.total_usage  (exato, não é amostragem);
      * CPU líquida  = CPU bruta - taxa_ociosa x duração_da_carga;
      * throttling   = Δ throttled_periods / Δ throttled_time (cota CFS de 0,5 vCPU);
      * memória      = working set (usage - inactive_file), amostrada a ~4 Hz.
 Todos os 3 contêineres de uma tecnologia são somados.

Todos os contêineres possuem exatamente o mesmo limite (0,5 vCPU, 256 MiB),
portanto as diferenças refletem o custo da tecnologia, não da infraestrutura.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import random
import threading
import time
from datetime import datetime

import lab_utils as lab
import multiprotocol_random_stress_test as mp
from final_benchmark import _call, warmup

MIB = 1024 * 1024


_STAT_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=6)


def _read_all(names):
    names = list(names)
    res = list(_STAT_POOL.map(lab.read_container_stats, names))
    return dict(zip(names, res))


def measure_protocol(proto: str, per_service: int, concurrency: int, warm: int, idle_s: int, seed: int) -> dict:
    names = lab.container_names(proto)
    combos = [(s, proto) for s in lab.SERVICES]
    mp.RUN_ID = int(time.time() * 1000)
    warmup(combos, warm)
    time.sleep(1.0)

    # --- janela ociosa -------------------------------------------------------
    a = _read_all(names)
    time.sleep(idle_s)
    b = _read_all(names)
    idle_cpu_rate = {n: (b[n]["cpu_ns"] - a[n]["cpu_ns"]) / 1e9 / (b[n]["t"] - a[n]["t"]) for n in names}
    mem_idle = sum(b[n]["mem_bytes"] for n in names)

    # --- janela de carga -----------------------------------------------------
    plan = [(s, i) for s in lab.SERVICES for i in range(1, per_service + 1)]
    random.Random(seed).shuffle(plan)
    start = _read_all(names)
    samples = []
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            try:
                samples.append(_read_all(names))
            except Exception:
                pass
            stop.wait(0.15)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()

    def one(item):
        k, (svc, i) = item
        el, ok, err = _call(svc, proto, 10_000 * (lab.SERVICES.index(svc) + 1) + i)
        return ok, el, err

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        results = list(ex.map(one, enumerate(plan, 1)))
    wall = time.perf_counter() - t0
    stop.set()
    th.join(timeout=5)
    end = _read_all(names)

    total = len(plan)
    lat_ok = [r[1] for r in results if r[0]]
    client = lab.summarize(lat_ok, total, wall)

    # CPU exata (soma dos 3 contêineres)
    cpu_gross_s = sum((end[n]["cpu_ns"] - start[n]["cpu_ns"]) for n in names) / 1e9
    load_dur = max(end[n]["t"] for n in names) - min(start[n]["t"] for n in names)
    idle_cpu_total = sum(idle_cpu_rate.values()) * load_dur
    cpu_net_s = max(cpu_gross_s - idle_cpu_total, 0.0)

    thr_periods = sum(end[n]["throttled_periods"] - start[n]["throttled_periods"] for n in names)
    thr_s = sum(end[n]["throttled_ns"] - start[n]["throttled_ns"] for n in names) / 1e9

    # CPU instantânea (janelas >= 0.25 s entre amostras) e memória por instante
    mem_series = []
    cpu_windows = []
    last = None
    for s in samples:
        mem_series.append(sum(s[n]["mem_bytes"] for n in names))
        if last is None:
            last = s
            continue
        dt = s[names[0]]["t"] - last[names[0]]["t"]
        if dt >= 0.25:
            cpu_windows.append(sum(s[n]["cpu_ns"] - last[n]["cpu_ns"] for n in names) / 1e9 / dt * 100.0)
            last = s
    if not mem_series:
        mem_series = [sum(end[n]["mem_bytes"] for n in names)]
    mem_after = sum(end[n]["mem_bytes"] for n in names)
    mean_pct = round(cpu_gross_s / load_dur * 100.0, 2) if load_dur > 0 else 0.0
    peak_pct = round(max([mean_pct] + cpu_windows), 2)

    return {
        "protocol": proto,
        "containers": names,
        "requests": total,
        "concurrency": concurrency,
        "client": client,
        "cpu": {
            "gross_cpu_seconds": round(cpu_gross_s, 4),
            "idle_cpu_seconds_estimated": round(idle_cpu_total, 4),
            "net_cpu_seconds": round(cpu_net_s, 4),
            "net_cpu_ms_per_request": round(cpu_net_s * 1000.0 / total, 4),
            "gross_cpu_ms_per_request": round(cpu_gross_s * 1000.0 / total, 4),
            # % de 1 vCPU, somando os 3 contêineres, médio na janela de carga
            "mean_pct_of_one_core": mean_pct,
            "peak_pct_of_one_core_1s": peak_pct,
            "idle_pct_of_one_core": round(sum(idle_cpu_rate.values()) * 100.0, 3),
            "throttled_periods": thr_periods,
            "throttled_seconds": round(thr_s, 4),
            "load_duration_s": round(load_dur, 3),
            "quota_pct_of_one_core_total": 150.0,  # 3 contêineres x 0,5 vCPU
        },
        "memory": {
            "idle_mib": round(mem_idle / MIB, 2),
            "mean_during_load_mib": round(sum(mem_series) / len(mem_series) / MIB, 2),
            "peak_during_load_mib": round(max(mem_series) / MIB, 2),
            "after_load_mib": round(mem_after / MIB, 2),
            "growth_mib": round((mem_after - mem_idle) / MIB, 2),
            "limit_total_mib": round(sum(end[n]["mem_limit"] for n in names) / MIB, 2),
            "per_container_after_mib": {n: round(end[n]["mem_bytes"] / MIB, 2) for n in names},
            "samples": len(mem_series),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=list(lab.SCENARIOS), default="ideal")
    ap.add_argument("--per-service", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--idle-seconds", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    conc = lab.SCENARIOS[a.scenario]["resource_concurrency"]
    report = {"scenario": a.scenario, "per_service": a.per_service, "concurrency": conc,
              "timestamp": datetime.now().isoformat(), "protocols": {}}
    for proto in lab.PROTOCOLS:
        r = measure_protocol(proto, a.per_service, conc, a.warmup, a.idle_seconds, a.seed)
        report["protocols"][proto] = r
        c, m = r["cpu"], r["memory"]
        print(f"[{a.scenario}] RES {proto:<9} cpu_net={c['net_cpu_ms_per_request']} ms/req "
              f"mean={c['mean_pct_of_one_core']}% peak={c['peak_pct_of_one_core_1s']}% "
              f"thr={c['throttled_periods']} mem_peak={m['peak_during_load_mib']} MiB "
              f"ok={r['client']['success']}/{r['requests']}")
    lab.save_json(os.path.join(a.outdir, f"resources_{a.scenario}.json"), report)


if __name__ == "__main__":
    main()
