import time
import xml.etree.ElementTree as ET

import pytest
import requests

BASE_URL = "http://localhost:8006/soap/users"
HEALTH_URL = "http://localhost:8006/health"
METRICS_URL = "http://localhost:8006/metrics"


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
                print("✅ Serviço SOAP User disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SOAP User não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_wsdl_available():
    resp = requests.get(BASE_URL)
    assert resp.status_code == 200
    assert "UserService" in resp.text
    assert "GetUser" in resp.text
    assert "CreateUser" in resp.text


def test_create_and_get_user():
    email = f"soap_user_{time.time_ns()}@example.com"
    create_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>SOAP User</name>
      <email>{email}</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>"""
    create_resp = requests.post(BASE_URL, data=create_body, headers={"Content-Type": "text/xml"})
    assert create_resp.status_code == 200
    created = _find(ET.fromstring(create_resp.content), "CreateUserResponse")
    assert _find(created, "email").text == email
    user_id = _find(created, "id").text

    get_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUser>
      <id>{user_id}</id>
    </GetUser>
  </soap:Body>
</soap:Envelope>"""
    get_resp = requests.post(BASE_URL, data=get_body, headers={"Content-Type": "text/xml"})
    assert get_resp.status_code == 200
    found = _find(ET.fromstring(get_resp.content), "GetUserResponse")
    assert _find(found, "email").text == email


def test_duplicate_email_conflict():
    email = f"soap_dup_{time.time_ns()}@example.com"
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateUser>
      <name>Dup User</name>
      <email>{email}</email>
    </CreateUser>
  </soap:Body>
</soap:Envelope>"""
    first = requests.post(BASE_URL, data=body, headers={"Content-Type": "text/xml"})
    assert first.status_code == 200
    second = requests.post(BASE_URL, data=body, headers={"Content-Type": "text/xml"})
    assert second.status_code == 409
    assert _find(ET.fromstring(second.content), "Fault") is not None


def test_get_user_not_found():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUser>
      <id>999999</id>
    </GetUser>
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
