import os
import time
import logging
import asyncio
import time
import json
import uuid
import aiomysql
import asyncpg
from httpx import AsyncClient
from typing import MutableMapping
from aio_pika import connect, ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue, AbstractIncomingMessage
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from starlette.background import BackgroundTask, BackgroundTasks

# TODO: Utiliser BaseSetting du module pydantic_settings
LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO)) # CRITICAL = 50 / ERROR = 40 / WARNING = 30 / INFO = 20 / DEBUG = 10 / NOTSET = 0
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mysql")

USE_MYSQL = DATABASE_TYPE == "mysql"
USE_POSTGRES = DATABASE_TYPE == "postgresql"

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", 5672)
RABBITMQ_MANAGEMENT_PORT = os.getenv("RABBITMQ_MANAGEMENT_PORT", 15672)
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

MYSQL_HOST = os.getenv("DB_HOST")
MYSQL_USER = os.getenv("DB_USER")
MYSQL_PASSWORD = os.getenv("DB_PASSWORD")
MYSQL_DB = os.getenv("DB_DATABASE")
MYSQL_PORT = int(os.getenv("DB_PORT", 3306))

POSTGRES_HOST = os.getenv("DB_HOST")
POSTGRES_USER = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
POSTGRES_DB = os.getenv("DB_DATABASE")
POSTGRES_PORT = int(os.getenv("DB_PORT", 5432))

app = FastAPI()

models ={
    "object": "list",
    "data": []
    } # object return by endpoint /v1/models
available_models = [] # list of available model names
async def update_available_models():
    # TODO: ajouter le exchange name en variable d'env et l'utiliser ici et dans le RPCClient
    global models
    global available_models
    http_client = AsyncClient(base_url=f"http://{RABBITMQ_HOST}:{RABBITMQ_MANAGEMENT_PORT}")
    response = await http_client.get(
        url=f"/api/exchanges/%2F/rpc/bindings/source", 
        auth=(RABBITMQ_USER, RABBITMQ_PASSWORD)
    )
    available_models = [binding["destination"] for binding in response.json()]
    models["data"] = [
                    {
                        "id" : binding["destination"],
                        "object" : "model",
                        "created": int(time.time()),
                        "owned_by": binding["destination"],
                    } for binding in response.json()
                    ]
    

async def verify_token(token):
    result = None
    if USE_MYSQL:
        connection = await aiomysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB
        )
        async with connection.cursor() as cursor:
            query = "SELECT * FROM users WHERE token = %s"
            await cursor.execute(query, (token,))
            result = await cursor.fetchone()
            logging.debug(" [x] Result type %r" % type(result))
            if result:
                logging.debug("Type result %r" % type(result[1]))
        connection.close()
    else:
        if not USE_POSTGRES:
            logging.warning("DATABASE_TYPE not specified, defaulting to postgresql")
        connection = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        try:
            query = "SELECT * FROM users WHERE token = $1"
            result = await connection.fetchrow(query, token)
            logging.debug(" [x] Result type %r" % type(result))
            if result:
                logging.debug("Type result %r" % type(result[1]))
        finally:
            await connection.close()
    return result


class RPCClient:
    connection: AbstractConnection
    channel: AbstractChannel
    callback_queue: AbstractQueue

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}

    async def connect(self) -> None:
        self.connection = await connect(url=RABBITMQ_URL)
        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        self.exchange = await self.channel.declare_exchange(
            name="rpc",
            type=ExchangeType.TOPIC,
            durable=True
        )
        self.consumer_tag = await self.callback_queue.consume(self.on_response, no_ack=True)

    async def close(self) -> None:
        logging.info("Closing RPC Connection")
        await self.callback_queue.cancel(self.consumer_tag)
        await self.connection.close()
        logging.info("RPC Connection closed")

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            print(f"Bad message {message!r}")
            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)
        future.set_result(message)

    async def call(self, priority: int, threshold: int, model: str) -> AbstractIncomingMessage | int:
        model_queue = await self.channel.get_queue(name=model)
        nb_messages = model_queue.declaration_result.message_count            
        logging.info(f"{nb_messages} messages in the model queue : {model}")
        if nb_messages > threshold:
            return 1
        
        logging.info(f" [x] New request for model {model}")
        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        await self.exchange.publish(
            message = Message(
                body=b"AVAILABLE?",
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
                priority=priority
            ),
            routing_key=model,
        )
        logging.info(f" [x] Message push to model queue {model}")
        response: AbstractIncomingMessage = await future
        logging.info(f" [.] For model {model}, got LLM URL")
        return response


@app.middleware("http")
async def proxy(request: Request, call_next):
    start = time.localtime()
    start_hour = f"{start.tm_hour}:{start.tm_min}:{start.tm_sec}"
    logging.info(f"Received request on path {request.url.path}")

    if request.method == "GET" and request.url.path == "/health":
        return PlainTextResponse(content="OK", status_code=200)
    
    # Authorization
    Authorization = request.headers.get("Authorization")
    if not Authorization:
        return JSONResponse(content={"error": "No token provided"}, status_code=401)
    token_parts = Authorization.split()
    if len(token_parts) != 2 or token_parts[0] != 'Bearer':
        return JSONResponse(content={"error": "Invalid token"}, status_code=401)
    user = await verify_token(token_parts[1])
    if not user:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    user_id, token, priority, threshold = user
    if threshold is None:
        threshold = 0
    logging.info("User fetched")

    # TODO: essayer d'utiliser callnext en gérer le cas où il n'y a pas d'endpoint défini
    if request.method == "GET":
        path = request.url.path
        if path == "/v1/models":
            await update_available_models()
            return JSONResponse(content=models, status_code=200)
        else:
            return JSONResponse(content={"error": "404 Not Found"}, status_code=404)

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
            status_code=404
        )
    
    requested_model = json_body["model"]
    if requested_model not in available_models:
        await update_available_models()
        if requested_model not in available_models:
            return JSONResponse(content={"error": "Unknown model"}, status_code=404)

    # Send and listen for RPC
    # TODO: sortir le rpclient du middleware pour n'en ouvrir qu'un et toujours utiliser le même
    rpc_client = RPCClient()
    await rpc_client.connect()
    logging.info("rpc client connected")
    rpc_response = await rpc_client.call(priority, threshold, requested_model)
    if type(rpc_response)==int:
        response_content = {"error": "Too many people using the service"}
        if json_body["stream"]:
            # in case of stream, we set status code to 200 to avoid OpenWebUI to crash
            # TODO: add an attribute in the database to know if its a streaming token or not rather than checking the JSON body as now.
            return PlainTextResponse(content=response_content, status_code=200)
        else:
            return JSONResponse(content=response_content, status_code=503)
    logging.info("rpc response received")
    
    llm_url = rpc_response.body.decode()
    logging.info(f"LLM Url received : {llm_url}")
    http_client = AsyncClient(base_url=llm_url, timeout=600.0)
    req = http_client.build_request(
        method=request.method,
        url=request.url.path,
        content=body
    )
    logging.info(f"request: \nmethod: {request.method}\nurl: {request.url.path}\ncontent: {body}")
    logging.info("async proxy request created")
    
    async def confirm():
        await rpc_client.channel.default_exchange.publish(
            message=Message(
                body=b"REQUEST LAUNCHED",
                correlation_id=rpc_response.correlation_id
            ),
            routing_key=rpc_response.reply_to
        )
    
    try:
        res = await http_client.send(req, stream=True)
        await confirm()
        logging.info("async proxy request send")
        background_tasks = BackgroundTasks([
            BackgroundTask(res.aclose),
            BackgroundTask(http_client.aclose),
            BackgroundTask(rpc_client.close),
            BackgroundTask(logging.info, f"Fin de la requête lancée à {start_hour}")
        ])
        return StreamingResponse(
            res.aiter_raw(),
            headers=res.headers,
            background=background_tasks
        )
    except Exception as e:
        logging.error(e)
        await confirm()
        await rpc_client.close()
        return JSONResponse(content={"error": "Internal error"}, status_code=500)


# if __name__=="__main__":
#     # TODO: proprement fermé les connexions rabbitmq lorsque le script est arrêté
#     # TODO: PORT en variable d'env ? 
#     uvicorn.run(app, port=8080, host="127.0.0.1")
