import os
import logging
import asyncio
import json
import aiomysql
import asyncpg
from aio_pika import connect, ExchangeType, Message, DeliveryMode, IncomingMessage
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO)) # CRITICAL = 50 / ERROR = 40 / WARNING = 30 / INFO = 20 / DEBUG = 10 / NOTSET = 0
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mysql")

USE_MYSQL = DATABASE_TYPE == "mysql"
USE_POSTGRES = DATABASE_TYPE == "postgres"

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", 5672)
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

MYSQL_HOST = os.getenv("DB_HOST")
MYSQL_USER = os.getenv("DB_USER")
MYSQL_PASSWORD = os.getenv("DB_PASSWORD")
MYSQL_DB = os.getenv("DB_DATABASE")
MYSQL_PORT = os.getenv("DB_PORT")

POSTGRES_HOST = os.getenv("DB_HOST")
POSTGRES_USER = os.getenv("DB_USER")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD")
POSTGRES_DB = os.getenv("DB_DATABASE")
POSTGRES_PORT = os.getenv("DB_PORT")


TIMEOUT = int(os.getenv("TIMEOUT", 30))

app = FastAPI()

async def verify_token(token):
    result = None
    if USE_MYSQL:
        connection = await aiomysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            port = MYSQL_PORT
        )
        async with connection.cursor() as cursor:
            query = "SELECT * FROM users WHERE token = %s"
            await cursor.execute(query, (token,))
            result = await cursor.fetchone()
            logging.debug(" [x] Result type %r" % type(result))
            if result:
                logging.debug("Type result %r" % type(result[1]))
        connection.close()
    elif USE_POSTGRES:
        connection = await asyncpg.connect(
            host=POSTGRES_HOST,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB, 
            port = POSTGRES_PORT
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

async def read_stream(callback_queue_name: str):
    work_queue = asyncio.Queue()
    async def handle_message(message: IncomingMessage):
        await work_queue.put(message.body.decode())
        await message.ack()

    try:
        connection = await connect(url=RABBITMQ_URL)
        logging.debug(" [x] Response connected")
        channel = await connection.channel()
        callback_queue = await channel.get_queue(name=callback_queue_name)
        consumer_tag = await callback_queue.consume(callback=handle_message)

        data = await work_queue.get()
        while data != "data: [DONE]\n\n" and data != "data: Internal error\n\n":
            logging.debug(" [x] Yielding data %r" % data)
            yield data
            data = await work_queue.get()

        await callback_queue.cancel(consumer_tag=consumer_tag)
        await callback_queue.delete()
        await connection.close()
        yield data
    except Exception as e:
        logging.error(e)

async def read_no_stream(callback_queue_name: str):
    work_queue = asyncio.Queue()
    async def handle_message(message: IncomingMessage):
        await work_queue.put(message.body.decode())
        await message.ack()
    
    try:
        connection = await connect(url=RABBITMQ_URL)
        logging.debug(" [x] Response connected")
        channel = await connection.channel()
        callback_queue = await channel.get_queue(name=callback_queue_name)
        consumer_tag = await callback_queue.consume(callback=handle_message)
        data = await work_queue.get()
        logging.debug(f"    Data type : {type(data)}")
        logging.debug(f"    Data : {data}")
        
        if data == "data: Internal error\n\n":
            response = JSONResponse(
                content={"error": "Internal error"},
                status_code=500,
                media_type="application/json"
            )
        else:
            response = JSONResponse(
                content=json.loads(data),
                status_code=200,
                media_type="application/json"
            )
        
        await callback_queue.cancel(consumer_tag=consumer_tag)
        await callback_queue.delete()
        await connection.close()
        return response
    except Exception as e:
        logging.error(e)

class Chat(BaseModel):
    role: str
    content: str

class Chat_Body(BaseModel):
    messages: list[Chat]
    model: str
    stream: bool = False

@app.post("/v1/chat/completions")
async def chat_completion(body: Chat_Body, Authorization: str = Header(None)):
    if not Authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    token_parts = Authorization.split()
    if len(token_parts) != 2 or token_parts[0] != 'Bearer':
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await verify_token(token_parts[1])
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    connection = await connect(url=RABBITMQ_URL)
    logging.info(" [x] Connected to RabbitMQ")
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    callback_queue = await channel.declare_queue()
    message = Message(
        body=body.model_dump_json().encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        reply_to=callback_queue.name,
        priority=user[2]
    )
    logging.debug(f" [x] Sending message {message.body}")
    await exchange.publish(message=message, routing_key="real-time")
    logging.info(" [x] Message sent")
    await connection.close()

    if body.stream:
        return StreamingResponse(
            content=read_stream(callback_queue.name),
            status_code=200,
            media_type="text/event-stream"
        )
    else:
        response = await read_no_stream(callback_queue.name)
        return response

@app.get("/health")
def health():
    return "OK"