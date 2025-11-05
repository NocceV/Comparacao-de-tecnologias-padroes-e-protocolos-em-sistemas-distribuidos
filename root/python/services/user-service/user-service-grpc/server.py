from prometheus_client import start_http_server, Counter, Histogram

# Métricas básicas
REQUEST_COUNT = Counter('grpc_requests_total', 'Total de chamadas gRPC', ['method'])
REQUEST_LATENCY = Histogram('grpc_request_latency_seconds', 'Latência por método', ['method'])

class UserService(user_pb2_grpc.UserServiceServicer):
    def GetUser(self, request, context):
        import time
        start = time.perf_counter()
        REQUEST_COUNT.labels(method='GetUser').inc()
        response = user_pb2.UserResponse(id=request.id, name=f"User{request.id}", email="user@example.com")
        REQUEST_LATENCY.labels(method='GetUser').observe(time.perf_counter() - start)
        return response

def serve():
    # 🔥 Adiciona servidor HTTP de métricas na porta 50052
    start_http_server(50052)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server running on port 50051, metrics on 50052")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)
