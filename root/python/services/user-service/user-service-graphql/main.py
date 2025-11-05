# main.py
from fastapi import FastAPI
from ariadne import QueryType, make_executable_schema
from ariadne.asgi import GraphQL

type_defs = """
    type User {
      id: Int!
      name: String!
      email: String!
    }

    type Query {
      user(id: Int!): User
    }
"""

query = QueryType()

@query.field("user")
def resolve_user(*_, id):
    return {"id": id, "name": f"User{id}", "email": "user@example.com"}

schema = make_executable_schema(type_defs, query)
app = FastAPI()
app.mount("/graphql", GraphQL(schema, debug=True))

@app.get("/health")
def health():
    return {"status": "ok"}
