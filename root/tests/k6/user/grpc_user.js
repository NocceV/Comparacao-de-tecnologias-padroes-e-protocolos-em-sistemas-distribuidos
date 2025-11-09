import grpc from "k6/net/grpc";
import { check, sleep } from "k6";

export let options = {
  vus: 50,             // 50 usuários virtuais
  duration: "30s",     // duração do teste
  thresholds: {
    grpc_req_duration: ["p(95)<200"], // 95% das req abaixo de 200ms
  },
};

const client = new grpc.Client();
client.load([], "protos/user.proto");

const GRPC_SERVER_ADDR = "localhost:50051";

export default function () {
  client.connect(GRPC_SERVER_ADDR, { plaintext: true });

  const data = { id: Math.floor(Math.random() * 500) + 1 };
  const response = client.invoke("user.UserService/GetUser", data);

  check(response, {
    "status OK": (r) => r && r.status === grpc.StatusOK,
  });

  sleep(0.1);
  client.close();
}
