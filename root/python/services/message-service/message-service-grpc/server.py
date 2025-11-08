import grpc
from concurrent import futures
import time
from prometheus_client import start_http_server, Counter, Histogram
import protos.message_pb2 as message_pb2
import protos.message_pb2_grpc as message_pb2_grpc
from datetime import datetime

REQUEST_COUNT = Counter('grpc_requests_total', 'Total de chamadas gRPC', ['method'])
REQUEST_LATENCY = Histogram('grpc_request_latency_seconds', 'Latência por método', ['method'])

class MessageService(message_pb2_grpc.MessageServiceServicer):
    def SendMessage(self, request, context):
        start = time.perf_counter()
        REQUEST_COUNT.labels(method='SendMessage').inc()

        response = message_pb2.MessageResponse(
            id=request.id,
            sender=request.sender or "User1",
            content=request.content or "Mensagem padrão",
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        REQUEST_LATENCY.labels(method='SendMessage').observe(time.perf_counter() - start)
        return response

def serve():
    # Porta 50053 para métricas Prometheus
    start_http_server(50053)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(), server)
    server.add_insecure_port('[::]:50052')
    server.start()

    print("gRPC MessageService rodando na porta 50052, métricas em 50053")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
