import com.google.protobuf.Any;
import com.google.protobuf.ByteString;
import is_protoc_precompiled.protos.MyProto.MyMessage;
import org.junit.Test;

public class HelloProto {
    @Test
    public void buildMessage() {
        Any any = Any.newBuilder()
            .setTypeUrl("type.example.com/test")
            .setValue(ByteString.copyFromUtf8("hello"))
            .build();
        MyMessage msg = MyMessage.newBuilder()
            .setContent(any)
            .build();
        System.out.println(msg);
    }
}
