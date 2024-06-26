import asyncio
import logging
import signal

from aio_pika import connect, ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from llm import llm
from math import inf
from probes import prober
from rpc import rpc_client, RPCClient
from settings import settings


# === Set constants ===

MODEL = settings.MODEL
AVG_TOKEN_THRESHOLD = settings.AVG_TOKEN_THRESHOLD
NB_USER_THRESHOLD = settings.NB_USER_THRESHOLD

RABBITMQ_URL = settings.RABBITMQ_URL
LLM_URL = settings.LLM_URL

DEFAULT_RETRY = 10
WAIT_TIME = 0.5


# === Initialize global variables ==

shutdown_signal = asyncio.Event()


# === Utility functions ===

async def try_connect_to_rabbitmq(retry: int = DEFAULT_RETRY):
    connection = None
    for attempt in range(retry):
        try:
            connection = await connect(url=RABBITMQ_URL)
        except Exception as e:
            logging.debug(f"Attempt {attempt+1}/{retry} to connect consumer to RabbitMQ failed : {e}")
            await asyncio.sleep(attempt)
        else:
            return connection
    logging.error(f"Failed to connect consumer to RabbitMQ after {retry} attempts")
    raise Exception(f"Failed to connect consumer to RabbitMQ after {retry} attempts")

async def on_message_callback(message: AbstractIncomingMessage, rpc_client: RPCClient):
    global current_avg_token

    logging.info(f"Message consumed on queue {MODEL}")

    current_avg_token, current_nb_users = await llm.get_metrics()
    
    while current_avg_token < AVG_TOKEN_THRESHOLD and current_nb_users > NB_USER_THRESHOLD:
        await asyncio.sleep(WAIT_TIME)
        current_avg_token, current_nb_users = await llm.get_metrics()

    rpc_response = await rpc_client.call(
        routing_key=message.reply_to, 
        correlation_id=str(message.correlation_id)
    )
    
    logging.info("RPC response received")
    await message.ack()
    logging.info("Message ACK")


# === Main function ===

async def main():
    logging.debug("Connecting consumer to RabbitMQ...")
    connection = await try_connect_to_rabbitmq()
    logging.info("Consumer connected to RabbitMQ")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    rpc_exchange = await channel.declare_exchange(
        name="rpc",
        type=ExchangeType.TOPIC,
        durable=True
    )
    model_queue = await channel.declare_queue(name=MODEL, durable=True)
    logging.info(f"Queue {MODEL} declared on channel")
    await model_queue.bind(exchange=rpc_exchange, routing_key=MODEL)
    logging.info("Queue binded to RPC channel")
    
    logging.debug("Connecting to RPC...")
    await rpc_client.connect()
    logging.info("Client connected to RPC")

    await model_queue.consume(
        callback = lambda message: on_message_callback(message, rpc_client),
        no_ack=False
    )
    logging.info(f"Consumption of queue {MODEL}")

    await prober.set_started()
    
    # Consumer is running until shutdown signal is received
    # Until then, all action occurs in the on_message_callback
    await shutdown_signal.wait()

    logging.debug("Closing RPC connection...")
    await rpc_client.close()
    logging.debug("RPC disconnect")
    logging.debug("Closing consumer connection...")
    await connection.close()
    logging.info("Consumer connection closed")


# === Entry point ===

if __name__=="__main__":
    logging.info("Starting consumer")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown():
        logging.info("Shutting down consumer...")
        shutdown_signal.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    loop.run_until_complete(prober.setup())

    try:
        loop.run_until_complete(main())
    finally:
        loop.run_until_complete(prober.cleanup())
        loop.close()
