import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 50 },
    { duration: "1m", target: 50 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<200"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = "http://localhost:8012";

export default function () {
  const message = {
    user: `User_${__VU}_${__ITER}`,
    content: `Mensagem via K6 - ${__VU}_${__ITER}`,
  };

  const res = http.post(`${BASE_URL}/messages/create`, JSON.stringify(message), {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1);
}
