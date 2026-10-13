import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parent / "scripts" / "benchmark_delivery.py"
sys.modules.setdefault("requests", types.ModuleType("requests"))
spec = importlib.util.spec_from_file_location("benchmark_delivery_test", SCRIPT)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class FakeResponse:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self, **_kwargs):
        yield "event: connected"
        yield 'data: {"status": "connected"}'
        yield ""
        yield "event: user_created"
        yield 'data: {"email": "someone-else@example.com"}'
        yield ""
        yield "event: user_created"
        yield 'data: {"email": "bench-123@example.com"}'
        yield ""


class DeliveryTests(unittest.TestCase):
    def test_sse_requires_matching_event(self):
        with patch.object(delivery.requests, "get", return_value=FakeResponse(), create=True), patch.object(delivery.requests, "post", return_value=FakeResponse(), create=True):
            elapsed, ok = delivery.sse_delivery("http://test/sse", "http://test/create", "bench-123")
        self.assertTrue(ok)
        self.assertGreaterEqual(elapsed, 0)

    def test_webhook_requires_callback(self):
        class Receiver:
            def register(self, *_args):
                pass

            def expect(self, _token):
                pass

            def wait(self, _token):
                return None

        with patch.object(delivery, "_get_receiver", return_value=Receiver()), patch.object(delivery.requests, "post", return_value=FakeResponse(), create=True):
            _elapsed, ok = delivery.webhook_delivery("user", "http://test/hooks", "http://test/users", {"email": "bench-123@example.com"}, "bench-123")
        self.assertFalse(ok)

    def test_callback_token_is_read_from_each_service_payload(self):
        self.assertEqual(delivery._token({"event": "user_created", "data": {"email": "bench-1@example.com"}}), "bench-1")
        self.assertEqual(delivery._token({"event": "message_created", "data": {"content": "bench-2"}}), "bench-2")
        self.assertEqual(delivery._token({"event": {"source": "bench-3"}}), "bench-3")


if __name__ == "__main__":
    unittest.main()
