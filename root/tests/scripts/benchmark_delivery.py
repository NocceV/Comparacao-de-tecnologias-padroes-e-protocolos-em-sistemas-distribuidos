"""Medidas de ponta a ponta para os protocolos de entrega assíncrona."""

import atexit
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


DELIVERY_TIMEOUT = 5
_receiver = None
_receiver_lock = threading.Lock()


def _token(payload):
    data = payload.get("data") or payload.get("event") or payload
    if not isinstance(data, dict):
        return None
    if "email" in data:
        return data["email"].split("@", 1)[0]
    return data.get("content") or data.get("source")


class _CallbackReceiver(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self):
        self.pending = {}
        self.registered_services = set()
        self.lock = threading.Lock()
        port = int(os.getenv("BENCHMARK_CALLBACK_PORT", "8765"))
        super().__init__(("0.0.0.0", port), _CallbackHandler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def expect(self, token):
        event = threading.Event()
        with self.lock:
            self.pending[token] = [event, None]

    def delivered(self, token):
        with self.lock:
            item = self.pending.get(token)
            if item is not None:
                item[1] = time.perf_counter()
                item[0].set()

    def wait(self, token):
        with self.lock:
            event = self.pending[token][0]
        event.wait(DELIVERY_TIMEOUT)
        with self.lock:
            _event, received_at = self.pending.pop(token)
        return received_at

    def cancel(self, token):
        with self.lock:
            self.pending.pop(token, None)

    def register(self, service, registration_url):
        with self.lock:
            if service in self.registered_services:
                return
            callback_host = os.getenv("BENCHMARK_CALLBACK_HOST", "host.docker.internal")
            callback_url = f"http://{callback_host}:{self.server_port}/callback"
            response = requests.post(registration_url, json={"callback_url": callback_url}, timeout=DELIVERY_TIMEOUT)
            response.raise_for_status()
            self.registered_services.add(service)


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/callback":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            token = _token(payload)
            if token:
                self.server.delivered(token)
            self.send_response(200)
            self.end_headers()
        except (ValueError, json.JSONDecodeError):
            self.send_error(400)

    def log_message(self, *_args):
        pass


def _get_receiver():
    global _receiver
    with _receiver_lock:
        if _receiver is None:
            _receiver = _CallbackReceiver()
            atexit.register(_receiver.server_close)
            atexit.register(_receiver.shutdown)
    return _receiver


def prepare_webhook(service, registration_url):
    _get_receiver().register(service, registration_url)


def webhook_delivery(service, registration_url, create_url, payload, token):
    receiver = _get_receiver()
    receiver.register(service, registration_url)
    receiver.expect(token)
    started = time.perf_counter()
    try:
        response = requests.post(create_url, json=payload, timeout=DELIVERY_TIMEOUT)
        delivered_at = receiver.wait(token)
        elapsed = ((delivered_at or time.perf_counter()) - started) * 1000
        return elapsed, response.status_code == 200 and delivered_at is not None
    except Exception:
        receiver.cancel(token)
        raise


def sse_delivery(stream_url, create_url, token, *, params=None, json_body=None):
    started = time.perf_counter()
    with requests.get(stream_url, stream=True, timeout=DELIVERY_TIMEOUT) as stream:
        stream.raise_for_status()
        lines = stream.iter_lines(chunk_size=1, decode_unicode=True)

        def next_event():
            event_name = None
            event_data = None
            for line in lines:
                if not line:
                    if event_name is not None:
                        return event_name, event_data
                    continue
                if line.startswith("event: "):
                    event_name = line[7:]
                elif line.startswith("data: "):
                    event_data = json.loads(line[6:])
            raise RuntimeError("Fluxo SSE encerrado sem evento")

        if next_event()[0] != "connected":
            raise RuntimeError("Fluxo SSE não confirmou a conexão")
        response = requests.post(create_url, params=params, json=json_body, timeout=DELIVERY_TIMEOUT)
        if response.status_code != 200:
            return (time.perf_counter() - started) * 1000, False
        deadline = time.perf_counter() + DELIVERY_TIMEOUT
        while time.perf_counter() < deadline:
            event_name, event_data = next_event()
            if event_name != "connected" and isinstance(event_data, dict) and _token(event_data) == token:
                return (time.perf_counter() - started) * 1000, True
        return (time.perf_counter() - started) * 1000, False
