import grpc
import protos.user_pb2 as user_pb2
import protos.user_pb2_grpc as user_pb2_grpc

channel = grpc.insecure_channel('localhost:50051')
stub = user_pb2_grpc.UserServiceStub(channel)
resp = stub.GetUser(user_pb2.GetUserRequest(id=1))
print(resp)