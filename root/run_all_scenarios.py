"""
ORQUESTRADOR AUTOMÁTICO DA BATERIA FINAL (3 cenários + resiliência + relatório)

Uso (dentro de `root/`):
    python run_all_scenarios.py                 # executa tudo, do zero
    python run_all_scenarios.py --resume RUN_ID # retoma uma execução interrompida
    python run_all_scenarios.py --quick         # versão curta, apenas para testar o pipeline

Etapas (cada uma é gravada em state.json e pode ser retomada):
  0. preparação : sobe o Docker Compose (limites idênticos de CPU/RAM), aguarda
                  health-check, constrói o sidecar do netem, registra o ambiente
                  e executa a validação funcional (pytest).
  1. grpc_variation : experimento controlado do gRPC (rede ideal).
  2. para cada cenário (ideal, realista, crítico):
        aplica netem -> determinístico + estocástico -> CPU/memória ->
        remove netem -> snapshot do Prometheus.
  3. resiliência : falhas de conexão (blackout e restart de contêiner).
  4. relatório   : gráficos, tabelas LaTeX/Markdown e guia de decisão.

Não requer intervenção: os logs ficam em results/final/<RUN_ID>/orchestrator.log.
A rede é sempre restaurada ao final (mesmo em caso de erro).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, "tests", "scripts")
INFRA = os.path.join(ROOT, "infra")
FINAL_DIR = os.path.join(ROOT, "tests", "results", "final")
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable

sys.path.insert(0, SCRIPTS)
import lab_utils as lab  # noqa: E402

SCENARIO_ORDER = ["ideal", "realista", "critico"]


class Run:
    def __init__(self, run_id: str, quick: bool):
        self.id = run_id
        self.quick = quick
        self.dir = os.path.join(FINAL_DIR, run_id)
        os.makedirs(self.dir, exist_ok=True)
        self.log_path = os.path.join(self.dir, "orchestrator.log")
        self.state_path = os.path.join(self.dir, "state.json")
        self.state = {"done": [], "errors": {}}
        if os.path.exists(self.state_path):
            self.state = json.load(open(self.state_path, encoding="utf-8"))

    def log(self, msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def done(self, stage: str) -> bool:
        return stage in self.state["done"]

    def mark(self, stage: str, error: str | None = None):
        if error:
            self.state["errors"][stage] = error
        else:
            if stage not in self.state["done"]:
                self.state["done"].append(stage)
            self.state["errors"].pop(stage, None)
        json.dump(self.state, open(self.state_path, "w", encoding="utf-8"), indent=2)

    def py(self, args: list, label: str, timeout: int | None = None) -> int:
        """Executa um script Python do diretório tests/scripts, ecoando a saída no log."""
        self.log(f"▶ {label}: {' '.join(args)}")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = SCRIPTS
        p = subprocess.Popen([PY] + args, cwd=SCRIPTS, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        t0 = time.time()
        with open(self.log_path, "a", encoding="utf-8") as lf:
            for line in p.stdout:  # type: ignore
                lf.write("    " + line)
                lf.flush()
                if timeout and time.time() - t0 > timeout:
                    p.kill()
                    self.log(f"⏱ {label} excedeu {timeout}s e foi interrompido")
                    break
        p.wait()
        self.log(f"{'✅' if p.returncode == 0 else '❌'} {label} terminou (código {p.returncode}) em {time.time() - t0:.0f}s")
        return p.returncode


def keep_awake():
    if sys.platform == "win32":
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: impede a suspensão do Windows durante a bateria
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


def release_awake():
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def sh_out(cmd: list, timeout: int = 60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace").stdout.strip()
    except Exception as e:
        return f"erro: {e}"


def stage_prepare(run: Run, skip_up: bool):
    if run.done("prepare"):
        return
    run.log("== ETAPA 0: preparação do ambiente ==")
    if not skip_up:
        r = subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=INFRA, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        run.log(f"docker compose up -> código {r.returncode}")
    if not lab.wait_all_healthy(420):
        raise RuntimeError("Nem todos os serviços ficaram saudáveis no tempo limite")
    lab.ensure_sidecar_image()
    lab.netem_clear_all(lab.container_names())
    manifest = {
        "run_id": run.id,
        "started_at": datetime.now().isoformat(),
        "host": {"os": platform.platform(), "python": platform.python_version(),
                 "docker": sh_out(["docker", "version", "--format", "{{.Server.Version}}"]),
                 "docker_info": sh_out(["docker", "info", "--format",
                                        "CPUs={{.NCPU}} MemTotal={{.MemTotal}} Kernel={{.KernelVersion}}"])},
        "git_commit": sh_out(["git", "rev-parse", "HEAD"], 15),
        "git_dirty": bool(sh_out(["git", "status", "--porcelain"], 15)),
        "limits_per_service_container": {"cpus": 0.5, "mem": "256MiB", "swap": "desabilitado", "pids": 256,
                                         "fonte": "infra/docker-compose.yml (x-service-limits)"},
        "containers": lab.container_health_report(),
        "scenarios": lab.SCENARIOS,
        "parameters": {"deterministic_requests_per_combination": run.params["det"],
                       "stochastic_requests_per_combination": run.params["sto"],
                       "warmup_per_combination": run.params["warm"],
                       "resource_requests_per_service": run.params["res"],
                       "grpc_variation_repetitions": run.params["grpc_rep"],
                       "resilience_variants": run.params["variants"],
                       "shuffle_seed": 42},
        "network_emulation": "tc netem na interface eth0 de cada contêiner de serviço (caminho de resposta)",
    }
    lab.save_json(os.path.join(run.dir, "manifest.json"), manifest)
    # Validação funcional (não bloqueante). Executada por domínio, pois os módulos de teste usam
    # o mesmo nome de pacote (`protos`) em cada pasta e colidiriam em uma única sessão do pytest.
    run.log("Executando validação funcional (pytest por domínio)...")
    summary, outputs = {}, []
    for dom in ("user", "message", "event"):
        r = subprocess.run([PY, "-m", "pytest", os.path.join(ROOT, "tests", "validacao_funcional", dom), "-q", "-p",
                            "no:cacheprovider", "--tb=line"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        summary[dom] = {"returncode": r.returncode, "resumo": last}
        outputs.append(f"===== {dom} =====\n{r.stdout}\n{r.stderr}")
        run.log(f"pytest [{dom}] -> código {r.returncode}: {last}")
    with open(os.path.join(run.dir, "functional_tests.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(outputs))
    lab.save_json(os.path.join(run.dir, "functional_tests_summary.json"), summary)
    run.mark("prepare")


def stage_grpc(run: Run):
    if run.done("grpc_variation"):
        return
    run.log("== ETAPA 1: experimento de variação do gRPC ==")
    lab.netem_clear_all(lab.container_names())
    rc = run.py(["grpc_variation_experiment.py", "--repetitions", str(run.params["grpc_rep"]),
                 "--gap-calls", str(run.params["gap"]), "--outdir", run.dir], "grpc_variation")
    run.mark("grpc_variation", None if rc == 0 else f"código {rc}")


def stage_scenario(run: Run, sc: str):
    stage = f"scenario_{sc}"
    if run.done(stage):
        return
    spec = lab.SCENARIOS[sc]
    outdir = os.path.join(run.dir, sc)
    os.makedirs(outdir, exist_ok=True)
    run.log(f"== CENÁRIO {spec['label'].upper()}: {spec['description']} ==")
    names = lab.container_names()
    lab.netem_clear_all(names)
    lab.wait_all_healthy(180)
    time.sleep(7)
    lab.save_json(os.path.join(outdir, "prometheus_before.json"), lab.prometheus_snapshot())
    ok = lab.apply_scenario_network(sc, names)
    bad = [n for n, v in ok.items() if not v]
    run.log(f"netem aplicado ({spec['delay_ms']}±{spec['jitter_ms']} ms, perda {spec['loss_pct']}%) "
            f"falhas={bad if bad else 'nenhuma'}")
    shows = {n: lab.netem_show(n) for n in ("user-grpc", "message-websocket", "event-rest")}
    lab.save_json(os.path.join(outdir, "netem_status.json"), {"applied": ok, "sample_qdisc": shows})
    err = None
    try:
        rc1 = run.py(["final_benchmark.py", "--regime", "both", "--scenario", sc,
                      "--det-requests", str(run.params["det"]), "--sto-per-combo", str(run.params["sto"]),
                      "--warmup", str(run.params["warm"]), "--seed", "42", "--outdir", outdir],
                     f"latência/vazão [{sc}]")
        rc2 = run.py(["resource_benchmark.py", "--scenario", sc, "--per-service", str(run.params["res"]),
                      "--idle-seconds", str(run.params["idle"]), "--outdir", outdir], f"CPU/memória [{sc}]")
        if rc1 or rc2:
            err = f"final_benchmark={rc1} resource_benchmark={rc2}"
    finally:
        lab.netem_clear_all(names)
        lab.wait_all_healthy(180)
        time.sleep(7)
        lab.save_json(os.path.join(outdir, "prometheus_after.json"), lab.prometheus_snapshot())
        lab.save_json(os.path.join(outdir, "containers_after.json"), lab.container_health_report())
    run.mark(stage, err)


def stage_resilience(run: Run):
    if run.done("resilience"):
        return
    run.log("== ETAPA 3: resiliência a falhas de conexão ==")
    lab.netem_clear_all(lab.container_names())
    rc = run.py(["resilience_test.py", "--outdir", run.dir, "--variants", run.params["variants"]], "resiliência")
    run.mark("resilience", None if rc == 0 else f"código {rc}")


def stage_report(run: Run):
    run.log("== ETAPA 4: geração do relatório e dos materiais ==")
    rc = run.py(["generate_final_report.py", "--run-dir", run.dir], "relatório")
    run.mark("report", None if rc == 0 else f"código {rc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default=None, help="RUN_ID de uma execução a retomar")
    ap.add_argument("--quick", action="store_true", help="parâmetros reduzidos (teste do pipeline)")
    ap.add_argument("--skip-up", action="store_true", help="não executar 'docker compose up'")
    ap.add_argument("--scenarios", default=",".join(SCENARIO_ORDER))
    a = ap.parse_args()

    run_id = a.resume or datetime.now().strftime("final_%Y%m%d_%H%M%S")
    run = Run(run_id, a.quick)
    run.params = ({"det": 10, "sto": 2, "warm": 2, "res": 40, "idle": 3, "grpc_rep": 2, "gap": 10,
                   "variants": "websocket,grpc"} if a.quick else
                  {"det": 100, "sto": 10, "warm": 3, "res": 100, "idle": 5, "grpc_rep": 8, "gap": 30,
                   "variants": "rest,soap,graphql,webhook,sse,websocket,grpc,grpc_tuned"})
    run.log(f"######## BATERIA FINAL {run_id} (quick={a.quick}) ########")
    keep_awake()
    try:
        stage_prepare(run, a.skip_up)
        stage_grpc(run)
        for sc in a.scenarios.split(","):
            try:
                stage_scenario(run, sc)
            except Exception:
                run.log(f"❌ erro no cenário {sc}:\n{traceback.format_exc()}")
                run.mark(f"scenario_{sc}", traceback.format_exc()[-400:])
        try:
            stage_resilience(run)
        except Exception:
            run.log(f"❌ erro na resiliência:\n{traceback.format_exc()}")
            run.mark("resilience", traceback.format_exc()[-400:])
        stage_report(run)
        run.log("🎉 BATERIA FINAL CONCLUÍDA. Resultados em: " + run.dir)
    except Exception:
        run.log(f"❌ ERRO FATAL:\n{traceback.format_exc()}")
        run.mark("fatal", traceback.format_exc()[-400:])
        raise
    finally:
        try:
            lab.netem_clear_all(lab.container_names())
        except Exception:
            pass
        release_awake()


if __name__ == "__main__":
    main()
