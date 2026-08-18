#include <iostream>

#include "google/protobuf/any.pb.h"
#include "protos/my_proto.pb.h"

int main() {
    is_protoc_precompiled::protos::MyMessage msg;
    google::protobuf::Any any;
    any.set_type_url("type.example.com/test");
    any.set_value("hello");
    *msg.mutable_content() = any;
    std::cout << msg.DebugString() << std::endl;
    return 0;
}
