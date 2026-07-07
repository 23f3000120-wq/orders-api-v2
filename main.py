from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from collections import defaultdict
import uuid
import time
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 46
RATE_LIMIT = 18
WINDOW = 10

orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]
idempotency_store = {}
client_requests = defaultdict(list)


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id")

    if client_id:
        now = time.time()

        client_requests[client_id] = [
            t for t in client_requests[client_id]
            if now - t < WINDOW
        ]

        if len(client_requests[client_id]) >= RATE_LIMIT:
            retry_after = int(
                WINDOW - (now - client_requests[client_id][0])
            ) + 1

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        client_requests[client_id].append(now)

    return await call_next(request)


@app.get("/")
def root():
    return {"message": "Orders API is running"}


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/orders")
def create_order(idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Missing Idempotency-Key"
        )

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    idempotency_store[idempotency_key] = order

    return JSONResponse(
        status_code=201,
        content=order
    )


@app.get("/orders")
def get_orders(limit: int = 10, cursor: Optional[str] = None):
    start = 0

    if cursor:
        start = int(base64.b64decode(cursor.encode()).decode())

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
