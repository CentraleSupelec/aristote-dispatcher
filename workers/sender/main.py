import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from aio_pika.exceptions import ChannelClosed
from db import Database
from exceptions import InvalidTokenException, NoTokenException, UnauthorizedException
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from httpx import AsyncClient
from models import get_model_by_id, get_models
from rpc_client import RPCClient
from settings import Settings
from starlette.background import BackgroundTask, BackgroundTasks

settings = Settings()

database = None
rpc_client = None

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.info("Opening database connection")
    global database
    database = await Database.init_database(settings=settings)
    logging.info("Database connection opened")

    logging.info("Opening RPC connection")
    global rpc_client
    rpc_client = RPCClient(settings=settings)
    await rpc_client.first_connect()
    logging.info("RPC connection opened")

    yield

    await database.close()
    await rpc_client.close()


app = FastAPI(lifespan=lifespan)


async def authorize(request: Request):

    authorization = request.headers.get("Authorization")

    if not authorization:
        raise NoTokenException()

    token_parts = authorization.split()

    if len(token_parts) != 2 or token_parts[0] != "Bearer":
        raise InvalidTokenException()

    user = await database.execute(
        "SELECT * FROM users WHERE token = %s",
        "SELECT * FROM users WHERE token = $1",
        token_parts[1],
    )

    if not user:
        raise UnauthorizedException()

    return user


@app.get("/v1/models")
async def models():
    return JSONResponse(content=await get_models(settings), status_code=200)


@app.middleware("http")
async def proxy(request: Request, call_next):
    start = time.localtime()
    start_hour = f"{start.tm_hour}:{start.tm_min}:{start.tm_sec}"
    logging.info("Received request on path %s", request.url.path)

    if request.method == "GET" and request.url.path == "/health/liveness":
        return PlainTextResponse(content="OK", status_code=200)

    # Readiness check is useful as sender can be loadbalanced
    if request.method == "GET" and request.url.path == "/health/readiness":
        state = await rpc_client.check_connection()
        if state:
            return PlainTextResponse(content="OK", status_code=200)
        return PlainTextResponse(content="KO", status_code=503)

    # Authorization
    try:
        user = await authorize(request)
    except (NoTokenException, InvalidTokenException, UnauthorizedException) as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
    user_id, _, priority, threshold, client_type = user
    threshold = 0 if threshold is None else threshold

    logging.info("User %s authorized", user_id)

    # Handle GET request normally
    if request.method == "GET":
        return await call_next(request)

    body = await request.body()
    try:
        json_body = json.loads(body)
    except json.decoder.JSONDecodeError:
        return JSONResponse(content={"error": "Invalid JSON Body"}, status_code=400)

    # Handle request without model in the body
    if not json_body["model"]:
        return JSONResponse(
            content={
                "object": "error",
                "message": "No model specified.",
                "type": "NotFoundError",
            },
            status_code=404,
        )

    requested_model = json_body["model"]

    if not await get_model_by_id(settings, requested_model):
        return JSONResponse(
            content={
                "object": "error",
                "error": "Unknown model",
            },
            status_code=404,
        )

    try:
        rpc_response = await rpc_client.call(priority, threshold, requested_model)
    except ChannelClosed:
        # the queue may have been deleted (ex: consumer does not exist anymore)
        logging.debug(
            "Queue %s seems to not be existing anymore. Refreshing models...",
            requested_model,
        )
        asyncio.create_task(get_models(settings))
        return JSONResponse(
            content={
                "object": "error",
                "error": "Unknown model",
            },
            status_code=404,
        )

    if isinstance(rpc_response, int):
        response_content = {"error": "Too many people using the service"}
        match client_type:
            case "chat":
                return JSONResponse(content=response_content, status_code=200)
            case _:
                return JSONResponse(content=response_content, status_code=503)

    logging.info("RPC response received")

    llm_params = json.loads(rpc_response.body.decode())
    llm_url = llm_params["llmUrl"]
    llm_token = llm_params["llmToken"]

    if llm_url == "None":
        return JSONResponse(
            content={
                "object": "error",
                "error": f"{requested_model} is busy, try again later",
            },
            status_code=503,
        )

    headers = {}
    if llm_token:
        headers["Authorization"] = f"Bearer {llm_token}"
    logging.info("LLM Url received : %s", llm_url)

    http_client = AsyncClient(base_url=llm_url, timeout=300.0)
    req = http_client.build_request(
        method=request.method, url=request.url.path, content=body, headers=headers
    )

    logging.info("Request ( Method: %s ; URL: %s )", request.method, request.url.path)
    logging.debug(" > Request content: %s", body)

    res = await http_client.send(req, stream=True)
    logging.info("Proxy request sent")
    background_tasks = BackgroundTasks(
        [
            BackgroundTask(res.aclose),
            BackgroundTask(http_client.aclose),
            BackgroundTask(logging.info, f"Finished request started at {start_hour}"),
        ]
    )
    return StreamingResponse(
        res.aiter_raw(), headers=res.headers, background=background_tasks
    )
