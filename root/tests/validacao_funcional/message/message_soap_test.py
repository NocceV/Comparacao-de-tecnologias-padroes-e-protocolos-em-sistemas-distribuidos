import time
import xml.etree.ElementTree as ET

import pytest
import requests

BASE_URL = "http://localhost:8016/soap/messages"
HEALTH_URL = "http://localhost:8016/health"
METRICS_URL = "http://localhost:8016/metrics"


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _find(root, tag):
    for el in root.iter():
        if _local(el.tag) == tag:
            return el
    return None


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    for _ in range(10):
        try:
            r = requests.get(HEALTH_URL)
            if r.status_code == 200:
                print("✅ Serviço SOAP Message disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SOAP Message não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_wsdl_available():
    resp = requests.get(BASE_URL)
    assert resp.status_code == 200
    assert "MessageService" in resp.text
    assert "CreateMessage" in resp.text


def test_create_and_get_message():
    content = f"Mensagem de teste {time.time_ns()}"
    create_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateMessage>
      <user>Vitor</user>
      <content>{content}</content>
    </CreateMessage>
  </soap:Body>
</soap:Envelope>"""
    create_resp = requests.post(BASE_URL, data=create_body, headers={"Content-Type": "text/xml"})
    assert create_resp.status_code == 200
    created = _find(ET.fromstring(create_resp.content), "CreateMessageResponse")
    assert _find(created, "content").text == content
    message_id = _find(created, "id").text

    get_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMessage>
      <id>{message_id}</id>
    </GetMessage>
  </soap:Body>
</soap:Envelope>"""
    get_resp = requests.post(BASE_URL, data=get_body, headers={"Content-Type": "text/xml"})
    assert get_resp.status_code == 200
    found = _find(ET.fromstring(get_resp.content), "GetMessageResponse")
    assert _find(found, "content").text == content


def test_invalid_message_rejected():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateMessage>
      <user>ab</user>
      <content>oi</content>
    </CreateMessage>
  </soap:Body>
</soap:Envelope>"""
    resp = requests.post(BASE_URL, data=body, headers={"Content-Type": "text/xml"})
    assert resp.status_code == 400
    assert _find(ET.fromstring(resp.content), "Fault") is not None


def test_get_message_not_found():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMessage>
      <id>999999</id>
    </GetMessage>
  </soap:Body>
</soap:Envelope>"""
    resp = requests.post(BASE_URL, data=body, headers={"Content-Type": "text/xml"})
    assert resp.status_code == 404
    assert _find(ET.fromstring(resp.content), "Fault") is not None


def test_metrics_exposed():
    resp = requests.get(METRICS_URL)
    assert resp.status_code == 200
    content = resp.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    print("📊 Métricas coletadas com sucesso!")
