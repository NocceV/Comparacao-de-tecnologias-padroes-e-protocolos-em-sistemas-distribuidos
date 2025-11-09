import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 50 },   // Sobe até 50 usuários virtuais
    { duration: "1m", target: 50 },    // Sustenta carga
    { duration: "20s", target: 0 },    // Diminui gradualmente
  ],
  thresholds: {
    http_req_duration: ["p(95)<400"], // 95% das requisições abaixo de 400ms
    http_req_failed: ["rate<0.01"],   // Menos de 1% de falhas
  },
};

const BASE_URL = "http://localhost:8023";

export default function () {
  const event = {
    id: Math.floor(Math.random() * 1000),
    type: "load_test_event",
    source: "k6",
    timestamp: new Date().toISOString(),
  };

  const res = http.post(`${BASE_URL}/events`, JSON.stringify(event), {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1); // pequena pausa entre requisições
}
