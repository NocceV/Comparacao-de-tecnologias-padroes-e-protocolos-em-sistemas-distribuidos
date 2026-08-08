import time
import xml.etree.ElementTree as ET

import pytest
import requests

BASE_URL = "http://localhost:8026/soap/events"
HEALTH_URL = "http://localhost:8026/health"
METRICS_URL = "http://localhost:8026/metrics"


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
                print("✅ Serviço SOAP Event disponível!")
                return
        except Exception:
            time.sleep(2)
    pytest.fail("❌ Serviço SOAP Event não iniciou a tempo.")


def test_healthcheck():
    resp = requests.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_wsdl_available():
    resp = requests.get(BASE_URL)
    assert resp.status_code == 200
    assert "EventService" in resp.text
    assert "CreateEvent" in resp.text


def test_create_and_get_event():
    source = f"soap_test_{time.time_ns()}"
    create_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateEvent>
      <type>publish</type>
      <source>{source}</source>
    </CreateEvent>
  </soap:Body>
</soap:Envelope>"""
    create_resp = requests.post(BASE_URL, data=create_body, headers={"Content-Type": "text/xml"})
    assert create_resp.status_code == 200
    created = _find(ET.fromstring(create_resp.content), "CreateEventResponse")
    assert _find(created, "type").text == "PUBLISH"
    assert _find(created, "status").text == "ENABLED"
    event_id = _find(created, "id").text

    get_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetEvent>
      <id>{event_id}</id>
    </GetEvent>
  </soap:Body>
</soap:Envelope>"""
    get_resp = requests.post(BASE_URL, data=get_body, headers={"Content-Type": "text/xml"})
    assert get_resp.status_code == 200
    found = _find(ET.fromstring(get_resp.content), "GetEventResponse")
    assert _find(found, "source").text == source


def test_toggle_event_status():
    create_body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateEvent>
      <type>update</type>
      <source>toggle-test</source>
    </CreateEvent>
  </soap:Body>
</soap:Envelope>"""
    create_resp = requests.post(BASE_URL, data=create_body, headers={"Content-Type": "text/xml"})
    event_id = _find(ET.fromstring(create_resp.content), "CreateEventResponse")
    event_id = _find(event_id, "id").text

    toggle_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ToggleEventStatus>
      <id>{event_id}</id>
    </ToggleEventStatus>
  </soap:Body>
</soap:Envelope>"""
    resp = requests.post(BASE_URL, data=toggle_body, headers={"Content-Type": "text/xml"})
    assert resp.status_code == 200
    toggled = _find(ET.fromstring(resp.content), "ToggleEventStatusResponse")
    assert _find(toggled, "status").text == "DISABLED"


def test_invalid_event_type_rejected():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <CreateEvent>
      <type>invalid_type</type>
      <source>x</source>
    </CreateEvent>
  </soap:Body>
</soap:Envelope>"""
    resp = requests.post(BASE_URL, data=body, headers={"Content-Type": "text/xml"})
    assert resp.status_code == 400
    assert _find(ET.fromstring(resp.content), "Fault") is not None


def test_get_event_not_found():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetEvent>
      <id>999999</id>
    </GetEvent>
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
