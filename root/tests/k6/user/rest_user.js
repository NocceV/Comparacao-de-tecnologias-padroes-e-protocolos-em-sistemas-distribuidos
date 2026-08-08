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

const BASE_URL = "http://localhost:8002";

export default function () {
  const name = `User_${__VU}_${__ITER}`;
  const email = `user_${__VU}_${__ITER}@example.com`;

  const res = http.post(`${BASE_URL}/user/create?name=${name}&email=${email}`);

  check(res, {
    "status 200": (r) => r.status === 200,
  });

  sleep(0.1);
}
