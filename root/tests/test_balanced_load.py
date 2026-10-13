import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tests" / "scripts"


def load_script(path):
    # Os handlers reais são substituídos nos testes; não há chamadas HTTP.
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BalancedLoadTests(unittest.TestCase):
    def test_multi_service_schedule_with_and_without_concurrency(self):
        module = load_script(SCRIPTS / "multiprotocol_random_stress_test.py")
        for concurrency in (1, 4):
            with self.subTest(concurrency=concurrency), tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
                calls = Counter()

                def handler(service, protocol):
                    def execute(_index):
                        calls[service, protocol] += 1
                        return 1.0, True
                    return execute

                registry = {
                    service: {protocol: handler(service, protocol) for protocol in ("rest", "soap")}
                    for service in ("user", "message", "event")
                }
                output = Path(directory) / "report.json"
                with patch.object(module, "REGISTRY", registry), contextlib.redirect_stdout(io.StringIO()):
                    module.run_multiprotocol_test(requests_per_target=5, concurrency=concurrency, output_file=str(output))

                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["total_requests"], 30)
                self.assertEqual(report["requests_per_target"], 5)
                self.assertEqual(set(calls.values()), {5})
                self.assertEqual(len(calls), 6)
                self.assertEqual({key: value["requests"] for key, value in report["protocols"].items()}, {"rest": 15, "soap": 15})

    def test_service_schedules_are_balanced(self):
        for service in ("user", "message", "event"):
            with self.subTest(service=service), tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
                module = load_script(SCRIPTS / service / f"{service}_random_stress_test.py")
                calls = Counter()

                def handler(protocol):
                    def execute(_index):
                        calls[protocol] += 1
                        return 1.0, True
                    return execute

                handlers = {protocol: handler(protocol) for protocol in ("rest", "soap", "sse")}
                output = Path(directory) / "report.json"
                with patch.object(module, "PROTOCOL_HANDLERS", handlers), contextlib.redirect_stdout(io.StringIO()):
                    module.run_random_stress_test(requests_per_protocol=4, output_file=str(output))

                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["total_requests"], 12)
                self.assertEqual(report["requests_per_protocol"], 4)
                self.assertEqual(calls, {"rest": 4, "soap": 4, "sse": 4})

    def test_missing_targets_fail_before_load(self):
        module = load_script(SCRIPTS / "multiprotocol_random_stress_test.py")
        with patch.object(module, "REGISTRY", {"user": {"rest": lambda _index: (1.0, True)}}):
            with self.assertRaisesRegex(ValueError, "Esperados 21 alvos"):
                module.run_multiprotocol_test(expected_targets=21)

    def test_orchestrator_passes_per_target_count(self):
        module = load_script(ROOT / "run_app.py")
        with patch.object(module.subprocess, "run") as run, patch.object(module.os.path, "exists", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            module.run_stochastic_suite(requests_per_target=7)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--requests") + 1], "7")
        self.assertEqual(command[command.index("--expected-targets") + 1], "21")


if __name__ == "__main__":
    unittest.main()
