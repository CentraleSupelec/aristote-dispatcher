import json
import logging
import time
from contextlib import asynccontextmanager
from db import Database
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from httpx import AsyncClient
from models import get_model_by_id, get_models
from rpc_client import RPCClient
from settings import Settings
from starlette.background import BackgroundTask, BackgroundTasks


settings = Settings()

database = None
rpc_client = None

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Opening database connection")
    global database
    database = await Database.init_database(settings=settings)
    logging.info("Database connection opened")

    logging.info("Opening RPC connection")
    global rpc_client
    rpc_client = RPCClient(settings=settings)
    await rpc_client.connect()
    logging.info("RPC connection opened")

    yield

    await database.close()
    await rpc_client.close()


app = FastAPI(lifespan=lifespan)

async def authorize(request: Request):

    authorization = request.headers.get("Authorization")

    if not authorization:
        raise Exception("NO_TOK")

    token_parts = authorization.split()

    if len(token_parts) != 2 or token_parts[0] != "Bearer":
        raise Exception("INV_TOK")

    user = await database.execute(
        "SELECT * FROM users WHERE token = %s",
        "SELECT * FROM users WHERE token = $1",
        token_parts[1],
    )

    if not user:
        raise Exception("UNAUTH")

    return user


@app.get("/v1/models")
async def models():
    return JSONResponse(content=await get_models(settings), status_code=200)

@app.middleware("http")
async def proxy(request: Request, call_next):
    start = time.localtime()
    start_hour = f"{start.tm_hour}:{start.tm_min}:{start.tm_sec}"
    logging.info(f"Received request on path {request.url.path}")

    if request.method == "GET" and request.url.path == "/health/liveness":
        return PlainTextResponse(content="OK", status_code=200)

    # Readiness check is useful as sender can be loadbalanced
    if request.method == "GET" and request.url.path == "/health/readiness":
        state = await rpc_client.check_connection()
        if state:
            return PlainTextResponse(content="OK", status_code=200)
        else:
            return PlainTextResponse(content="KO", status_code=503)

    # Authorization
    try:
        user = await authorize(request)
    except Exception as e:
            match str(e):
                case "NO_TOK":
                    logging.error("No token provided")
                    return JSONResponse(content={"error": "No token provided"}, status_code=401)
                case "INV_TOK":
                    logging.error("Invalid token")
                    return JSONResponse(content={"error": "Invalid token"}, status_code=401)
                case "UNAUTH":
                    logging.error("Unauthorized")
                    return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
                case e:
                    logging.error(f"An unexpected error occurred while authorizing: {e}")
                    return JSONResponse(content={"An internal error occured"}, status_code=500)
    user_id, token, priority, threshold, client_type = user
    threshold = 0 if threshold is None else threshold

    logging.info(f"User {user_id} authorized")

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

    rpc_response = await rpc_client.call(priority, threshold, requested_model)

    if type(rpc_response) == int:
        response_content = {"error": "Too many people using the service"}
        match client_type:
            case "chat":
                return JSONResponse(content=response_content, status_code=200)
            case _:
                return JSONResponse(content=response_content, status_code=503)

    logging.info("rpc response received")

    llm_url = rpc_response.body.decode()
    logging.info(f"LLM Url received : {llm_url}")

    http_client = AsyncClient(base_url=llm_url, timeout=300.0)
    req = http_client.build_request(
        method=request.method, url=request.url.path, content=body
    )

    logging.info(
        f"request: \nmethod: {request.method}\nurl: {request.url.path}\ncontent: {body}"
    )
    logging.info("async proxy request created")

    try:
        res = await http_client.send(req, stream=True)
        logging.info("async proxy request send")
        background_tasks = BackgroundTasks(
            [
                BackgroundTask(res.aclose),
                BackgroundTask(http_client.aclose),
                BackgroundTask(
                    logging.info, f"Fin de la requête lancée à {start_hour}"
                ),
            ]
        )
    except Exception as e:
        logging.error(e)
        return JSONResponse(content={"error": "Internal error"}, status_code=500)
    else:
        return StreamingResponse(
            res.aiter_raw(), headers=res.headers, background=background_tasks
        )
