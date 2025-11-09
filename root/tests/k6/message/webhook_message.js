import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 50 },   // sobe até 50 usuários
    { duration: "1m", target: 50 },    // mantém carga
    { duration: "20s", target: 0 },    // encerra
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95% das requisições < 500ms
    http_req_failed: ["rate<0.01"],   // Menos de 1% de falhas
  },
};

const BASE_URL = "http://localhost:8004";

export function setup() {
  const callback_url = `${BASE_URL}/webhook/receiver`;
  const res = http.post(`${BASE_URL}/hooks/messages`, JSON.stringify({ callback_url }), {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "Webhook registrado": (r) => r.status === 200 });
  console.log("✅ Webhook registrado com sucesso antes do teste.");
}

export default function () {
  const message = {
    sender: `User_${__VU}_${__ITER}`,
    content: `Mensagem via K6 - ${__VU}_${__ITER}`,
  };

  const res = http.post(`${BASE_URL}/messages`, JSON.stringify(message), {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1);
}
