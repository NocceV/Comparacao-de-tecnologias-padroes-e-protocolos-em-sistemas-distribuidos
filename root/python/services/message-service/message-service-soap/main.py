from datetime import datetime
from typing import Dict, Optional
import time
import xml.etree.ElementTree as ET

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

app = FastAPI(title="Message SOAP")

_messages: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de mensagens",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de mensagens",
    ["endpoint"],
)

WSDL = """<?xml version="1.0"?>
<definitions name="MessageService"
    targetNamespace="http://example.com/messages"
    xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:tns="http://example.com/messages"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/">

  <message name="GetMessageRequest">
    <part name="id" type="xsd:int"/>
  </message>
  <message name="GetMessageResponse">
    <part name="message" type="tns:Message"/>
  </message>
  <message name="CreateMessageRequest">
    <part name="user" type="xsd:string"/>
    <part name="content" type="xsd:string"/>
  </message>
  <message name="CreateMessageResponse">
    <part name="message" type="tns:Message"/>
  </message>

  <portType name="MessageServicePortType">
    <operation name="GetMessage">
      <input message="tns:GetMessageRequest"/>
      <output message="tns:GetMessageResponse"/>
    </operation>
    <operation name="CreateMessage">
      <input message="tns:CreateMessageRequest"/>
      <output message="tns:CreateMessageResponse"/>
    </operation>
  </portType>

  <binding name="MessageServiceBinding" type="tns:MessageServicePortType">
    <soap:binding style="rpc" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetMessage">
      <soap:operation soapAction="GetMessage"/>
    </operation>
    <operation name="CreateMessage">
      <soap:operation soapAction="CreateMessage"/>
    </operation>
  </binding>

  <service name="MessageService">
    <port name="MessageServicePort" binding="tns:MessageServiceBinding">
      <soap:address location="http://localhost:8016/soap/messages"/>
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


def _message_xml(message: dict) -> str:
    return (
        f"<id>{message['id']}</id><user>{message['user']}</user>"
        f"<content>{message['content']}</content><timestamp>{message['timestamp']}</timestamp>"
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_local(element: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in element.iter():
        if _local_name(child.tag) == tag:
            return child
    return None


@app.get("/soap/messages")
def get_wsdl() -> Response:
    return Response(WSDL, media_type="text/xml")


@app.post("/soap/messages")
async def soap_messages(request: Request) -> Response:
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

    if op_name == "GetMessage":
        id_el = _find_local(operation, "id")
        message = _messages.get(int(id_el.text)) if id_el is not None else None
        if message is None:
            response_xml, status_code = _fault("Message not found"), 404
        else:
            response_xml, status_code = _envelope(f"<GetMessageResponse>{_message_xml(message)}</GetMessageResponse>"), 200

    elif op_name == "CreateMessage":
        user_el = _find_local(operation, "user")
        content_el = _find_local(operation, "content")
        user = user_el.text if user_el is not None else None
        content = content_el.text if content_el is not None else None

        if user is None or not (3 <= len(user) <= 30) or not content:
            response_xml, status_code = _fault("Invalid user or content"), 400
        else:
            message = {
                "id": _next_id,
                "user": user,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
            _messages[_next_id] = message
            _next_id += 1
            response_xml, status_code = _envelope(f"<CreateMessageResponse>{_message_xml(message)}</CreateMessageResponse>"), 200

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
