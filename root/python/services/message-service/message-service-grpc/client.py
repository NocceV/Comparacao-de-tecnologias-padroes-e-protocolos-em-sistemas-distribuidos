import grpc
import protos.message_pb2 as message_pb2
import protos.message_pb2_grpc as message_pb2_grpc

channel = grpc.insecure_channel('localhost:50052')
stub = message_pb2_grpc.MessageServiceStub(channel)

req = message_pb2.SendMessageRequest(id=1, sender="Vitor", content="Mensagem teste via gRPC")
resp = stub.SendMessage(req)

print("Resposta:", resp)
