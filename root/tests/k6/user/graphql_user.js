import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Rampa até 50 usuários
    { duration: '1m', target: 50 },    // Sustenta carga
    { duration: '20s', target: 0 },    // Reduz usuários
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'], // 95% das requisições < 800ms
    http_req_failed: ['rate<0.01'],   // Menos de 1% de falhas
  },
};

const GRAPHQL_URL = 'http://localhost:8001/graphql';

const query = `
  query {
    user(id: 1) {
      id
      name
      email
    }
  }
`;

export default function () {
  const headers = { 'Content-Type': 'application/json' };
  const res = http.post(GRAPHQL_URL, JSON.stringify({ query }), { headers });

  check(res, {
    'status 200': (r) => r.status === 200,
    'tem dados válidos': (r) => r.body.includes('User1'),
  });

  sleep(0.2); // pequena pausa entre requisições
}
