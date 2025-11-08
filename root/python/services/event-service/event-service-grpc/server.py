import grpc
from concurrent import futures
import time
from prometheus_client import start_http_server, Counter, Histogram
import protos.event_pb2 as event_pb2
import protos.event_pb2_grpc as event_pb2_grpc

REQUEST_COUNT = Counter('grpc_requests_total', 'Total de chamadas gRPC', ['method'])
REQUEST_LATENCY = Histogram('grpc_request_latency_seconds', 'Latência por método', ['method'])
EVENT_COUNT = Counter('grpc_events_emitted_total', 'Total de eventos emitidos')

class EventService(event_pb2_grpc.EventServiceServicer):
    def StreamEvents(self, request, context):
        REQUEST_COUNT.labels(method='StreamEvents').inc()
        print(f"Stream iniciado com filtro: {request.filter}")
        try:
            while True:
                start = time.perf_counter()
                event = event_pb2.Event(
                    id=int(time.time()),
                    type="system_update",
                    source="event-service-grpc",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    status="emitted"
                )
                yield event
                EVENT_COUNT.inc()
                REQUEST_LATENCY.labels(method='StreamEvents').observe(time.perf_counter() - start)
                time.sleep(3)  # Envia um evento a cada 3 segundos
        except grpc.RpcError:
            print("Cliente desconectado do stream.")

    def EmitEvent(self, request, context):
        start = time.perf_counter()
        REQUEST_COUNT.labels(method='EmitEvent').inc()
        print(f"Evento recebido: {request.type} de {request.source}")
        response = event_pb2.Event(
            id=int(time.time()),
            type=request.type,
            source=request.source,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            status="emitted"
        )
        EVENT_COUNT.inc()
        REQUEST_LATENCY.labels(method='EmitEvent').observe(time.perf_counter() - start)
        return response


def serve():
    print("🚀 Iniciando Event gRPC Service...")
    start_http_server(50062)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    event_pb2_grpc.add_EventServiceServicer_to_server(EventService(), server)
    server.add_insecure_port('[::]:50061')
    server.start()
    print("gRPC server rodando na porta 50061, métricas em 50062")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
