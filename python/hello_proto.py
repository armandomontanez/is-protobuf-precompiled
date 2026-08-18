from google.protobuf import any_pb2
from protos import my_proto_pb2

msg = my_proto_pb2.MyMessage()
msg.content.Pack(any_pb2.Any())
print(msg)
