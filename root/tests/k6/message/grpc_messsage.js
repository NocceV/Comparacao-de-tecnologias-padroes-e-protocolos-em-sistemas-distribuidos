import grpc from "k6/net/grpc";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 50 },   // sobe até 50 usuários
    { duration: "1m", target: 50 },    // mantém carga
    { duration: "20s", target: 0 },    // encerra
  ],
  thresholds: {
    grpc_req_duration: ["p(95)<800"],  // 95% das reqs abaixo de 800ms
  },
};

const client = new grpc.Client();
client.load(["../protos"], "message.proto");

export default function () {
  client.connect("localhost:50054", { plaintext: true });

  const data = {
    id: Math.floor(Math.random() * 10000),
    sender: "k6User",
    content: "Mensagem de carga via K6",
  };

  const response = client.invoke("message.MessageService/SendMessage", data);

  check(response, {
    "status OK": (r) => r && r.status === grpc.StatusOK,
  });

  client.close();
  sleep(0.1);
}
