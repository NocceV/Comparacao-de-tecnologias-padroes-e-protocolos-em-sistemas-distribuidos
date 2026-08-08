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

const BASE_URL = "http://localhost:8016/soap/messages";

export default function () {
  const user = `User_${__VU}_${__ITER}`;
  const content = `Mensagem via K6 - ${__VU}_${__ITER}`;

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateMessage>
      <user>${user}</user>
      <content>${content}</content>
    </CreateMessage>
  </soap:Body>
</soap:Envelope>`;

  const res = http.post(BASE_URL, body, {
    headers: { "Content-Type": "text/xml", SOAPAction: "CreateMessage" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
    "contains CreateMessageResponse": (r) => r.body.includes("CreateMessageResponse"),
  });
}
