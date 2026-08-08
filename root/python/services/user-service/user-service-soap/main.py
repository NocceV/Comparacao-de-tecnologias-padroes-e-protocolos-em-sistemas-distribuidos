from typing import Dict, Optional
import time
import xml.etree.ElementTree as ET

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

app = FastAPI(title="User SOAP")

_users: Dict[int, dict] = {}
_next_id = 0

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP do servico de usuarios",
    ["method", "endpoint"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Tempo de resposta das requisicoes do servico de usuarios",
    ["endpoint"],
)

WSDL = """<?xml version="1.0"?>
<definitions name="UserService"
    targetNamespace="http://example.com/users"
    xmlns="http://schemas.xmlsoap.org/wsdl/"
    xmlns:tns="http://example.com/users"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/">

  <message name="GetUserRequest">
    <part name="id" type="xsd:int"/>
  </message>
  <message name="GetUserResponse">
    <part name="user" type="tns:User"/>
  </message>
  <message name="CreateUserRequest">
    <part name="name" type="xsd:string"/>
    <part name="email" type="xsd:string"/>
  </message>
  <message name="CreateUserResponse">
    <part name="user" type="tns:User"/>
  </message>

  <portType name="UserServicePortType">
    <operation name="GetUser">
      <input message="tns:GetUserRequest"/>
      <output message="tns:GetUserResponse"/>
    </operation>
    <operation name="CreateUser">
      <input message="tns:CreateUserRequest"/>
      <output message="tns:CreateUserResponse"/>
    </operation>
  </portType>

  <binding name="UserServiceBinding" type="tns:UserServicePortType">
    <soap:binding style="rpc" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetUser">
      <soap:operation soapAction="GetUser"/>
    </operation>
    <operation name="CreateUser">
      <soap:operation soapAction="CreateUser"/>
    </operation>
  </binding>

  <service name="UserService">
    <port name="UserServicePort" binding="tns:UserServiceBinding">
      <soap:address location="http://localhost:8006/soap/users"/>
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


def _user_xml(user: dict) -> str:
    return f"<id>{user['id']}</id><name>{user['name']}</name><email>{user['email']}</email>"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_local(element: ET.Element, tag: str) -> Optional[ET.Element]:
    for child in element.iter():
        if _local_name(child.tag) == tag:
            return child
    return None


@app.get("/soap/users")
def get_wsdl() -> Response:
    return Response(WSDL, media_type="text/xml")


@app.post("/soap/users")
async def soap_users(request: Request) -> Response:
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

    if op_name == "GetUser":
        id_el = _find_local(operation, "id")
        user = _users.get(int(id_el.text)) if id_el is not None else None
        if user is None:
            response_xml, status_code = _fault("User not found"), 404
        else:
            response_xml, status_code = _envelope(f"<GetUserResponse>{_user_xml(user)}</GetUserResponse>"), 200

    elif op_name == "CreateUser":
        name_el = _find_local(operation, "name")
        email_el = _find_local(operation, "email")
        name = name_el.text if name_el is not None else None
        email = email_el.text if email_el is not None else None

        if any(existing_user["email"] == email for existing_user in _users.values()):
            response_xml, status_code = _fault("Email already exists"), 409
        else:
            user = {"id": _next_id, "name": name, "email": email}
            _users[_next_id] = user
            _next_id += 1
            response_xml, status_code = _envelope(f"<CreateUserResponse>{_user_xml(user)}</CreateUserResponse>"), 200

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
