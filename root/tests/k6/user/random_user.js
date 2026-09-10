import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Counter } from "k6/metrics";

export const options = {
  stages: [
    { duration: "20s", target: 20 },
    { duration: "40s", target: 50 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<300"],
    http_req_failed: ["rate<0.05"],
  },
};

// Métricas separadas por protocolo
const protoTrends = {
  rest: new Trend("duration_rest"),
  graphql: new Trend("duration_graphql"),
  soap: new Trend("duration_soap"),
  webhook: new Trend("duration_webhook"),
  sse: new Trend("duration_sse"),
};

const protoCounters = {
  rest: new Counter("requests_rest"),
  graphql: new Counter("requests_graphql"),
  soap: new Counter("requests_soap"),
  webhook: new Counter("requests_webhook"),
  sse: new Counter("requests_sse"),
};

const PROTOCOLS = ["rest", "graphql", "soap", "webhook", "sse"];

export default function () {
  const chosen = PROTOCOLS[Math.floor(Math.random() * PROTOCOLS.length)];
  const runId = Date.now();
  const userName = `User_${__VU}_${__ITER}`;
  const userEmail = `user_rnd_${chosen}_${runId}_${__VU}_${__ITER}@example.com`;

  let res;

  if (chosen === "rest") {
    res = http.post(
      `http://localhost:8002/user/create?name=${userName}&email=${userEmail}`,
      null,
      { tags: { protocol: "rest" } }
    );
  } else if (chosen === "graphql") {
    const payload = JSON.stringify({
      query: `query { user(id: ${__ITER + 1}) { id name email } }`,
    });
    res = http.post("http://localhost:8001/graphql", payload, {
      headers: { "Content-Type": "application/json" },
      tags: { protocol: "graphql" },
    });
  } else if (chosen === "soap") {
    const body = `<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>${userName}</name>
      <email>${userEmail}</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>`;
    res = http.post("http://localhost:8006/soap/users", body, {
      headers: { "Content-Type": "text/xml", SOAPAction: "CreateUser" },
      tags: { protocol: "soap" },
    });
  } else if (chosen === "webhook") {
    const payload = JSON.stringify({ name: userName, email: userEmail });
    res = http.post("http://localhost:8003/users", payload, {
      headers: { "Content-Type": "application/json" },
      tags: { protocol: "webhook" },
    });
  } else if (chosen === "sse") {
    res = http.post(
      `http://localhost:8007/user/create?name=${userName}&email=${userEmail}`,
      null,
      { tags: { protocol: "sse" } }
    );
  }

  const success = check(res, {
    "status 200": (r) => r.status === 200,
  });

  if (protoTrends[chosen]) {
    protoTrends[chosen].add(res.timings.duration);
    protoCounters[chosen].add(1);
  }

  sleep(0.05);
}
