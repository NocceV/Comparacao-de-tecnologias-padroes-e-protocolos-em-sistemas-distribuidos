import http from "k6/http";
import { check, sleep } from "k6";

export let options = {
  vus: 50,              // 50 usuários virtuais
  duration: "30s",      // duração do teste
  thresholds: {
    http_req_duration: ["p(95)<200"], // 95% das req devem responder < 200ms
  },
};

const BASE_URL = "http://localhost:8003";

// Pré-teste: registrar webhook (executa uma vez antes dos VUs)
export function setup() {
  const callback = `${BASE_URL}/webhook/receiver`;
  const res = http.post(`${BASE_URL}/hooks/users`, JSON.stringify({ callback_url: callback }), {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "Webhook registrado com sucesso": (r) => r.status === 200 });
  return { callback };
}

// Teste de carga
export default function (data) {
  const user = {
    name: `User_${__VU}_${__ITER}`,
    email: `user_${__VU}_${__ITER}@example.com`,
  };

  let res = http.post(`${BASE_URL}/users`, JSON.stringify(user), {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1); // pequena pausa entre as requisições
}
