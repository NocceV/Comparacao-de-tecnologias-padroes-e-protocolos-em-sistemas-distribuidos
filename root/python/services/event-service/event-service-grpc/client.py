import grpc
import protos.event_pb2 as event_pb2
import protos.event_pb2_grpc as event_pb2_grpc

channel = grpc.insecure_channel('localhost:50061')
stub = event_pb2_grpc.EventServiceStub(channel)

resp = stub.EmitEvent(event_pb2.Event(type="user_created", source="user-service"))
print("Emitido:", resp)

print("Iniciando stream de eventos...")
for event in stub.StreamEvents(event_pb2.EventRequest(filter="all")):
    print("Evento recebido:", event)
