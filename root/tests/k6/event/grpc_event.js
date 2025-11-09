import grpc from 'k6/net/grpc';
import { check, sleep } from 'k6';

const client = new grpc.Client();
client.load(['./protos'], 'event.proto');

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // sobe até 50 usuários
    { duration: '1m', target: 50 },    // mantém carga
    { duration: '20s', target: 0 },    // finaliza gradualmente
  ],
  thresholds: {
    grpc_req_duration: ['p(95)<400'], // 95% das requisições abaixo de 400ms
  },
};

export default () => {
  client.connect('localhost:50061', { plaintext: true });

  const response = client.invoke('event.EventService/EmitEvent', {
    id: Math.floor(Math.random() * 1000),
    type: 'LoadTest',
    source: 'k6',
    timestamp: '',
    status: '',
  });

  check(response, {
    'status OK': (r) => r && r.status === grpc.StatusOK,
  });

  sleep(0.1);
  client.close();
};
