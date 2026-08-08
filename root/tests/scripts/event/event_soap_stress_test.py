import requests
import time
import statistics

BASE_URL = "http://localhost:8026/soap/events"
TOTAL_REQUESTS = 500
HEADERS = {"Content-Type": "text/xml", "SOAPAction": "CreateEvent"}


def create_event(index):
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateEvent>
      <type>publish</type>
      <source>stress_test_{index}</source>
    </CreateEvent>
  </soap:Body>
</soap:Envelope>"""

    start = time.perf_counter()
    response = requests.post(BASE_URL, data=body, headers=HEADERS)
    elapsed = (time.perf_counter() - start) * 1000
    status = response.status_code
    status_text = "OK" if status == 200 else "ERRO"
    print(f"Evento {index} criado - Status: {status} {status_text} - Tempo: {elapsed:.0f}ms")
    return elapsed


def main():
    print("=== TESTE DE STRESS - SOAP EVENT ===")

    latencies = []
    start_total = time.perf_counter()

    for i in range(1, TOTAL_REQUESTS + 1):
        latencies.append(create_event(i))

    total_time = (time.perf_counter() - start_total) * 1000
    avg_time = statistics.mean(latencies)
    min_time = min(latencies)
    max_time = max(latencies)
    throughput = TOTAL_REQUESTS / (total_time / 1000)

    print("\n=== RESULTADOS - TESTE DE STRESS (SOAP EVENT) ===")
    print(f"Total de requisições: {TOTAL_REQUESTS}")
    print(f"Tempo total do teste: {total_time:.0f}ms")
    print(f"Tempo médio por requisição: {avg_time:.0f}ms")
    print(f"Menor tempo de resposta: {min_time:.0f}ms")
    print(f"Maior tempo de resposta: {max_time:.0f}ms")
    print(f"Requisições por segundo (throughput): {throughput:.2f}")


if __name__ == "__main__":
    main()
