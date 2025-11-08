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
        REQUEST_COUsNT.labels(method='StreamEvents').inc()
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

# Métodos Disponíveis
# 1. StreamEvents (Server Streaming)
# Quando um cliente conecta:

# Incrementa contador de requisições
# Recebe filtro do cliente (por enquanto só imprime)
# Entra em loop infinito enviando eventos a cada 3 segundos
# Gera evento com timestamp atual
# Envia via stream (yield)
# Incrementa contador de eventos emitidos
# Registra latência de cada evento
# Continua até cliente desconectar

# Diferença crítica: Não retorna 1 resposta, envia stream infinito!
# 2. EmitEvent (Unary RPC - normal)
# Quando recebe um evento:

# Marca tempo inicial
# Incrementa contadores
# Cria evento com dados recebidos + timestamp
# Registra latência
# Retorna evento criado (resposta única)

# Portas/Endpoints

# Porta 50061: Servidor gRPC (recebe chamadas + streams)
# Porta 50062: Métricas Prometheus
# Métodos:

# StreamEvents(filter) → stream de Events (infinito)
# EmitEvent(type, source) → Event (único)