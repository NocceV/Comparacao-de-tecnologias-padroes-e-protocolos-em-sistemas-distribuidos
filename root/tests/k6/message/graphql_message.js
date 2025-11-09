import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // rampa de subida
    { duration: '1m', target: 50 },    // mantém 50 usuários
    { duration: '20s', target: 0 },    // queda gradual
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'], // 95% das requisições em < 800ms
    http_req_failed: ['rate<0.01'],   // menos de 1% de falhas
  },
};

const GRAPHQL_URL = 'http://localhost:8011/graphql';

const query = `
  query {
    message(id: 1) {
      id
      sender
      content
      timestamp
    }
  }
`;

export default function () {
  const headers = { 'Content-Type': 'application/json' };
  const res = http.post(GRAPHQL_URL, JSON.stringify({ query }), { headers });

  check(res, {
    'status 200': (r) => r.status === 200,
    'resposta contém "Mensagem"': (r) => r.body.includes('Mensagem'),
  });

  sleep(0.2);
}
