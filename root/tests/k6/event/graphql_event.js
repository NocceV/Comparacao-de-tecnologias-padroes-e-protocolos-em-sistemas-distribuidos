import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // sobe para 50 usuários
    { duration: '1m', target: 50 },    // mantém carga
    { duration: '20s', target: 0 },    // encerra gradualmente
  ],
  thresholds: {
    http_req_duration: ['p(95)<600'], // 95% das requisições < 600ms
    http_req_failed: ['rate<0.01'],   // menos de 1% de falhas
  },
};

const GRAPHQL_URL = 'http://localhost:8021/graphql';

export default function () {
  const mutation = `
    mutation {
      publishEvent(type: "LoadTest", source: "k6") {
        id
        type
        source
        timestamp
        status
      }
    }
  `;

  const headers = { 'Content-Type': 'application/json' };
  const res = http.post(GRAPHQL_URL, JSON.stringify({ query: mutation }), { headers });

  check(res, {
    'status 200': (r) => r.status === 200,
    'resposta contém "emitted"': (r) => r.body.includes('published'),
  });

  sleep(0.2); // pequena pausa entre requisições
}
