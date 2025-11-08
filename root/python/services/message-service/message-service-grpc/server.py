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
    start_http_server(50053)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(), server)
    server.add_insecure_port('[::]:50054')
    server.start()

    print("gRPC MessageService rodando na porta 50054, métricas em 50053")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()


# Marca o tempo inicial
# Incrementa o contador de requisições gRPC
# Cria uma mensagem com os dados recebidos (ou valores padrão)
# Gera timestamp atual automaticamente
# Registra a latência da operação
# Retorna a mensagem serializada (formato binário)

# Portas/Endpoints

# Porta 50054: Servidor gRPC (recebe chamadas RPC)
# Porta 50053: Servidor HTTP com métricas Prometheus
# Método disponível: SendMessage(id, sender, content) → MessageResponse

# Caso de Uso
# Este código é típico de sistemas de mensageria de alta performance, permitindo:

# Enviar mensagens entre microsserviços de forma eficiente
# Sistemas de chat em tempo real (WhatsApp, Telegram)
# Filas de mensagens (Kafka-like)
# Comunicação entre backends em jogos online
# Timestamp gerado automaticamente no servidor (evita problemas de sincronização)

# Vantagem sobre REST: Para enviar 1000 mensagens/segundo, gRPC é ~10x mais rápido que POST /messages com JSON.
# Observação: Assim como nos outros exemplos, os dados não são persistidos. É um exemplo/protótipo de serviço gRPC de escrita com métricas.