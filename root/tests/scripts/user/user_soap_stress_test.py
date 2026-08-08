import requests
import time
import statistics

BASE_URL = "http://localhost:8006/soap/users"
TOTAL_REQUESTS = 500
HEADERS = {"Content-Type": "text/xml", "SOAPAction": "CreateUser"}
RUN_ID = int(time.time())


def create_user(index):
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>User{index}</name>
      <email>user{RUN_ID}_{index}@example.com</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>"""

    start = time.perf_counter()
    response = requests.post(BASE_URL, data=body, headers=HEADERS)
    elapsed = (time.perf_counter() - start) * 1000
    status = response.status_code
    print(f"Usuário {index} criado - Status: {status} {'OK' if status == 200 else 'ERRO'} - Tempo: {elapsed:.0f}ms")
    return elapsed


def main():
    print("=== TESTE DE STRESS - SOAP USER ===")

    tempos = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        tempos.append(create_user(i))

    total_time = (time.perf_counter() - start_total) * 1000
    avg_time = statistics.mean(tempos)
    min_time = min(tempos)
    max_time = max(tempos)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (SOAP USER) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
