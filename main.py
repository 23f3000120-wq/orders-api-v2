from fastapi import FastAPI, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import time
import base64

app = FastAPI()

# CORS for grader
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fixed catalog: IDs 1 to 46
orders = [{"id": i} for i in range(1, 47)]

# Store idempotency keys
idempotency_store = {}

# Rate limiter
client_requests = {}
RATE_LIMIT = 18
WINDOW = 10


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id", "unknown")

    now = time.time()

    if client_id not in client_requests:
        client_requests[client_id] = []

    client_requests[client_id] = [
        t for t in client_requests[client_id]
        if now - t < WINDOW
    ]

    if len(client_requests[client_id]) >= RATE_LIMIT:
        response = JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"}
        )
        response.headers["Retry-After"] = "10"
        return response

    client_requests[client_id].append(now)

    return await call_next(request)


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(
    order: dict,
    Idempotency_Key: Optional[str] = Header(None)
):
    # Return previous result for same key
    if Idempotency_Key and Idempotency_Key in idempotency_store:
        return idempotency_store[Idempotency_Key]

    new_id = len(idempotency_store) + 1

    new_order = {
        "id": new_id,
        **order
    }

    if Idempotency_Key:
        idempotency_store[Idempotency_Key] = new_order

    return new_order


@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: Optional[str] = None
):
    start = 0

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    items = orders[start:start + limit]

    next_cursor = None

    if start + limit < len(orders):
        next_cursor = base64.b64encode(
            str(start + limit).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }
