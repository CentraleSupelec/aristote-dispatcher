import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from aio_pika.exceptions import ChannelClosed
from db import Database
from entities import Metric, User
from exceptions import (
    InvalidTokenException,
    NoTokenException,
    ServerError,
    UnauthorizedException,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from httpx import AsyncClient
from models import get_model_by_id, get_models
from rpc_client import CallResult, RPCClient
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
    global database

    logging.info("Opening database connection")
    database = Database(settings)
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


def authorize(request: Request):

    authorization = request.headers.get("Authorization")

    if not authorization:
        raise NoTokenException()

    token_parts = authorization.split()

    if len(token_parts) != 2 or token_parts[0] != "Bearer":
        raise InvalidTokenException()

    with database.get_session() as session:
        user = session.query(User).filter_by(token=token_parts[1]).first()

    if not user:
        raise UnauthorizedException()

    return user


def save_metrics_to_db(metric: Metric):
    with database.get_session() as session:
        session.add(metric)
        session.commit()


@app.get("/v1/models")
async def models():
    return JSONResponse(
        content={"object": "list", "data": await get_models(settings)}, status_code=200
    )


@app.get("/v1/models/{model_id}")
async def model(model_id):
    model_data = await get_model_by_id(settings, model_id)
    if model_data is None:
        return JSONResponse(
            content={
                "object": "error",
                "message": f"model {model_id} not found",
                "type": "NotFoundError",
            },
            status_code=404,
        )

    return JSONResponse(model_data, status_code=200)


@app.middleware("http")
async def proxy(request: Request, call_next):
    start = datetime.now()
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
        user = authorize(request)
    except (NoTokenException, InvalidTokenException, UnauthorizedException) as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    threshold = 0 if user.threshold is None else user.threshold

    logging.info("User %s authorized", user.token)

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
        rpc_response = await rpc_client.call(user.priority, threshold, requested_model)
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

    if isinstance(rpc_response, CallResult):
        if rpc_response not in {CallResult.QUEUE_OVERLOADED, CallResult.TIMEOUT}:
            raise ServerError()

        response_content = {"error": "Too many people using the service"}
        match str(user.client_type):
            case "chat":
                return JSONResponse(content=response_content, status_code=200)
            case _:
                return JSONResponse(content=response_content, status_code=503)

    logging.info("RPC response received")

    llm_params = json.loads(rpc_response.body.decode())
    llm_url = llm_params["llmUrl"]
    llm_token = llm_params["llmToken"]

    if llm_url == "None":
        response_content = {
            "error": f"{requested_model} is busy, try again later",
        }
        match str(user.client_type):
            case "chat":
                return JSONResponse(content=response_content, status_code=200)
            case _:
                return JSONResponse(content=response_content, status_code=503)

    content_type = request.headers.get("content-type")

    if content_type is None:
        content_type = "application/json"

    headers = {"Content-Type": content_type}
    if llm_token:
        headers["Authorization"] = f"Bearer {llm_token}"

    logging.info("LLM Url received : %s", llm_url)

    priority = llm_params.get("priority", None)
    if priority is not None and isinstance(priority, int):
        json_body["priority"] = priority
        body = json.dumps(json_body)

    http_client = AsyncClient(base_url=llm_url, timeout=300.0)
    req = http_client.build_request(
        method=request.method, url=request.url.path, content=body, headers=headers
    )

    logging.info("Request ( Method: %s ; URL: %s )", request.method, request.url.path)
    logging.debug(" > Request content: %s", body)

    sent_to_llm_date = datetime.now()
    res = await http_client.send(req, stream=True)
    logging.info("Proxy request sent")

    body = await res.aread()
    response_json = json.loads(body)
    prompt_tokens = response_json.get("usage", {}).get("prompt_tokens")
    completion_tokens = response_json.get("usage", {}).get("completion_tokens")

    metric = Metric(
        user_name=user.name,
        model=requested_model,
        request_date=start,
        sent_to_llm_date=sent_to_llm_date,
        response_date=datetime.now(),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    background_tasks = BackgroundTasks(
        [
            BackgroundTask(res.aclose),
            BackgroundTask(http_client.aclose),
            BackgroundTask(logging.info, f"Finished request started at {start}"),
            BackgroundTask(save_metrics_to_db, metric),
        ]
    )

    return StreamingResponse(
        iter([body]),
        headers=res.headers,
        background=background_tasks,
    )
