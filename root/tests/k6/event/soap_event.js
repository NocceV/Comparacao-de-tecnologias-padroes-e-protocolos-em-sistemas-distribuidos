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

const BASE_URL = "http://localhost:8026/soap/events";

export default function () {
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateEvent>
      <type>publish</type>
      <source>k6_${__VU}_${__ITER}</source>
    </CreateEvent>
  </soap:Body>
</soap:Envelope>`;

  const res = http.post(BASE_URL, body, {
    headers: { "Content-Type": "text/xml", SOAPAction: "CreateEvent" },
  });

  check(res, {
    "status 200": (r) => r.status === 200,
    "contains CreateEventResponse": (r) => r.body.includes("CreateEventResponse"),
  });
}
