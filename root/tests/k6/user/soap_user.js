import http from "k6/http";
import { check } from "k6";

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

const BASE_URL = "http://localhost:8006/soap/users";
const RUN_ID = Date.now();

export default function () {
  const name = `User_${__VU}_${__ITER}`;
  const email = `user_${RUN_ID}_${__VU}_${__ITER}@example.com`;

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>${name}</name>
      <email>${email}</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>`;

  const res = http.post(BASE_URL, body, {
    headers: { "Content-Type": "text/xml", SOAPAction: "CreateUser" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
    "contains CreateUserResponse": (r) => r.body.includes("CreateUserResponse"),
  });
}
