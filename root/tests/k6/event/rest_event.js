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

const BASE_URL = "http://localhost:8022";

export default function () {
  const res = http.post(`${BASE_URL}/create?type=publish&source=k6`);

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1);
}
