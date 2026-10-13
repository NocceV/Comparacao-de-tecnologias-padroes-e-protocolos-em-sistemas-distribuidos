import asyncio
import contextlib
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(path):
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    sys.modules.setdefault("websockets", types.ModuleType("websockets"))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSocket:
    def __init__(self, events, response):
        self.events = events
        self.response = response

    async def __aenter__(self):
        self.events.append("enter")
        return self

    async def __aexit__(self, *_args):
        self.events.append("exit")

    async def send(self, _payload):
        self.events.append("send")

    async def recv(self):
        self.events.append("recv")
        return json.dumps({"event": self.response})


class WebSocketTimingTests(unittest.TestCase):
    def test_each_websocket_measurement_includes_connection_and_close(self):
        for service, response, standalone_handler, random_handler, multi_handler in (
            ("user", "user_created", "create_user", "req_websocket", "call_user_websocket"),
            ("message", "message_created", "send_message", "req_websocket", "call_message_websocket"),
            ("event", "event_published", "publish_event", "req_websocket", "call_event_websocket"),
        ):
            for filename, handler in (
                (SCRIPTS / service / f"{service}_websocket_stress_test.py", standalone_handler),
                (SCRIPTS / service / f"{service}_random_stress_test.py", random_handler),
                (SCRIPTS / "multiprotocol_random_stress_test.py", multi_handler),
            ):
                with self.subTest(service=service, script=filename.name):
                    module = load_script(filename)
                    events = []
                    original_clock = module.time.perf_counter

                    def clock():
                        events.append("clock")
                        return original_clock()

                    def connect(*_args, **_kwargs):
                        events.append("connect")
                        return FakeSocket(events, response)

                    module.websockets = types.SimpleNamespace(connect=connect)
                    if hasattr(module, "HAS_WEBSOCKETS"):
                        module.HAS_WEBSOCKETS = True

                    def run_immediate(coroutine):
                        try:
                            coroutine.send(None)
                        except StopIteration as completed:
                            return completed.value
                        raise AssertionError("O socket simulado não deve suspender a execução")

                    with patch.object(module.time, "perf_counter", clock), patch.object(module.asyncio, "run", run_immediate), contextlib.redirect_stdout(io.StringIO()):
                        result = getattr(module, handler)(1)
                        if asyncio.iscoroutine(result):
                            result = run_immediate(result)

                    self.assertEqual(events, ["clock", "connect", "enter", "send", "recv", "exit", "clock"])
                    if isinstance(result, tuple):
                        self.assertTrue(result[1])


if __name__ == "__main__":
    unittest.main()
