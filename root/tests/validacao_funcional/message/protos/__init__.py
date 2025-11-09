"""protos package for message-service-grpc

This file makes the `protos` directory a Python package so
imports like `import protos.message_pb2` work when running
the top-level server script.
"""

__all__ = ["message_pb2", "message_pb2_grpc"]
