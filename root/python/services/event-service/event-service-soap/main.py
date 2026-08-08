from datetime import datetime
from enum import Enum
from typing import Dict, Optional
import time
import xml.etree.ElementTree as ET

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


class EventType(str, Enum):
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class EventStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

app = FastAPI(title="Event SOAP")

_events: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de eventos",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de eventos",
    ["endpoint"],
)

WSDL = """<?xml version="1.0"?>
<definitions name="EventService"
    targetNamespace="http://example.com/events"
    xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:tns="http://example.com/events"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/">

  <message name="GetEventRequest">
    <part name="id" type="xsd:int"/>
  </message>
  <message name="GetEventResponse">
    <part name="event" type="tns:Event"/>
  </message>
  <message name="CreateEventRequest">
    <part name="type" type="xsd:string"/>
    <part name="source" type="xsd:string"/>
  </message>
  <message name="CreateEventResponse">
    <part name="event" type="tns:Event"/>
  </message>
  <message name="ToggleEventStatusRequest">
    <part name="id" type="xsd:int"/>
  </message>
  <message name="ToggleEventStatusResponse">
    <part name="event" type="tns:Event"/>
  </message>

  <portType name="EventServicePortType">
    <operation name="GetEvent">
      <input message="tns:GetEventRequest"/>
      <output message="tns:GetEventResponse"/>
    </operation>
    <operation name="CreateEvent">
      <input message="tns:CreateEventRequest"/>
      <output message="tns:CreateEventResponse"/>
    </operation>
    <operation name="ToggleEventStatus">
      <input message="tns:ToggleEventStatusRequest"/>
      <output message="tns:ToggleEventStatusResponse"/>
    </operation>
  </portType>

  <binding name="EventServiceBinding" type="tns:EventServicePortType">
    <soap:binding style="rpc" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetEvent">
      <soap:operation soapAction="GetEvent"/>
    </operation>
    <operation name="CreateEvent">
      <soap:operation soapAction="CreateEvent"/>
    </operation>
    <operation name="ToggleEventStatus">
      <soap:operation soapAction="ToggleEventStatus"/>
    </operation>
  </binding>

  <service name="EventService">
    <port name="EventServicePort" binding="tns:EventServiceBinding">
      <soap:address location="http://localhost:8026/soap/events"/>
    </port>
  </service>
</definitions>"""


def _envelope(body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>{body_xml}</soap:Body></soap:Envelope>'
    )


def _fault(message: str) -> str:
    return _envelope(f"<soap:Fault><faultcode>Client</faultcode><faultstring>{message}</faultstring></soap:Fault>")


def _event_xml(event: dict) -> str:
    return (
        f"<id>{event['id']}</id><type>{event['type']}</type><source>{event['source']}</source>"
        f"<status>{event['status']}</status><date>{event['date']}</date>"
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_local(element: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in element.iter():
        if _local_name(child.tag) == tag:
            return child
    return None


@app.get("/soap/events")
def get_wsdl() -> Response:
    return Response(WSDL, media_type="text/xml")


@app.post("/soap/events")
async def soap_events(request: Request) -> Response:
    global _next_id
    raw = await request.body()
    start = time.perf_counter()

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return Response(_fault("Malformed XML"), media_type="text/xml", status_code=400)

    body = _find_local(root, "Body")
    operation = next(iter(body), None) if body is not None else None
    if operation is None:
        return Response(_fault("Missing SOAP Body"), media_type="text/xml", status_code=400)

    op_name = _local_name(operation.tag)
    REQUEST_COUNT.labels(method="POST", endpoint=op_name).inc()

    if op_name == "GetEvent":
        id_el = _find_local(operation, "id")
        event = _events.get(int(id_el.text)) if id_el is not None else None
        if event is None:
            response_xml, status_code = _fault("Event not found"), 404
        else:
            response_xml, status_code = _envelope(f"<GetEventResponse>{_event_xml(event)}</GetEventResponse>"), 200

    elif op_name == "CreateEvent":
        type_el = _find_local(operation, "type")
        source_el = _find_local(operation, "source")
        source = source_el.text if source_el is not None else None

        try:
            event_type = EventType[(type_el.text if type_el is not None else "").upper()]
        except KeyError:
            response_xml, status_code = _fault("Invalid event type"), 400
        else:
            event = {
                "id": _next_id,
                "type": event_type.value,
                "source": source,
                "status": EventStatus.ENABLED.value,
                "date": datetime.now().isoformat(),
            }
            _events[_next_id] = event
            _next_id += 1
            response_xml, status_code = _envelope(f"<CreateEventResponse>{_event_xml(event)}</CreateEventResponse>"), 200

    elif op_name == "ToggleEventStatus":
        id_el = _find_local(operation, "id")
        event = _events.get(int(id_el.text)) if id_el is not None else None
        if event is None:
            response_xml, status_code = _fault("Event not found"), 404
        else:
            if event["status"] == EventStatus.ENABLED.value:
                event["status"] = EventStatus.DISABLED.value
            else:
                event["status"] = EventStatus.ENABLED.value
            response_xml, status_code = _envelope(f"<ToggleEventStatusResponse>{_event_xml(event)}</ToggleEventStatusResponse>"), 200

    else:
        response_xml, status_code = _fault(f"Unknown operation: {op_name}"), 400

    REQUEST_LATENCY.labels(endpoint=op_name).observe(time.perf_counter() - start)
    return Response(response_xml, media_type="text/xml", status_code=status_code)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
