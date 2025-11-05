from fastapi import FastAPI, Request
import httpx
import uuid, asyncio

app = FastAPI()
callbacks = []

@app.post("/hooks/users")
async def register_hook(payload: dict):
    callback_url = payload.get("callback_url")
    if callback_url:
        callbacks.append(callback_url)
        return {"status":"registered", "id": str(uuid.uuid4())}
    return {"error":"callback_url required"}, 400

@app.post("/users")
async def create_user(payload: dict):
    user = {"id": 1, "name": payload.get("name", "User1"), "email": payload.get("email","user@example.com")}
    async def dispatch():
        async with httpx.AsyncClient() as client:
            for cb in callbacks:
                try:
                    await client.post(cb, json={"event":"user_created","data":user})
                except Exception as e:
                    print("failed to send to", cb, e)
    asyncio.create_task(dispatch())
    return user

@app.post("/webhook/receiver")
async def webhook_receiver(payload: dict):
    print("received webhook:", payload)
    return {"status":"received"}
