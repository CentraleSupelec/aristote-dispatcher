import json
import logging
import random
from typing import List

from aio_pika import DeliveryMode, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)

from .exceptions import ServerNotFound, UnknownLocalPriorityModel
from .priority_handler import BasePriorityHandler
from .quality_of_service_policy.qos_policy import QualityOfServiceBasePolicy
from .settings import settings
from .strategy.server_selection_strategy import ServerSelectionStrategy
from .vllm_server import VLLMServer

# === Set constants ===

MODEL = settings.MODEL


class RPCServer:
    def __init__(
        self,
        url: str,
        strategy: ServerSelectionStrategy,
        quality_of_service_policy: QualityOfServiceBasePolicy,
        priority_handler: BasePriorityHandler,
    ) -> None:
        self.url = url
        self.strategy = strategy
        self.quality_of_service_policy = quality_of_service_policy
        self.priority_handler = priority_handler
        self.connection: AbstractConnection = None
        self.channel: AbstractChannel = None
        self.queue: AbstractQueue = None
        self.completion_queue: AbstractQueue = None
        self.current_parallel_requests: dict[VLLMServer, int] = {
            server: 0 for server in settings.VLLM_SERVERS
        }

    async def first_connect(self) -> None:
        logging.debug("Connecting consumer to RabbitMQ...")
        try:
            self.connection = await connect_robust(url=self.url)
            self.connection.reconnect_callbacks.add(self.reconnect_callback)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(
                name=MODEL,
                durable=True,
                arguments={
                    "x-expires": settings.RPC_QUEUE_EXPIRATION,
                    "x-message-ttl": settings.RPC_MESSAGE_EXPIRATION,
                    "x-max-priority": settings.RPC_MAX_PRIORITY,
                },
            )
            await self.queue.consume(
                self.on_message_callback,
            )
            self.completion_queue = await self.channel.declare_queue(
                name=f"{MODEL}_completed",
                durable=True,
                arguments={
                    "x-expires": settings.RPC_QUEUE_EXPIRATION,
                },
            )
            await self.completion_queue.consume(
                self.on_completion_callback,
            )
            for server in settings.VLLM_SERVERS:
                server_queue = await self.channel.declare_queue(
                    name=f"{MODEL}_{server.organization}_private",
                    durable=True,
                    arguments={
                        "x-expires": settings.RPC_QUEUE_EXPIRATION,
                    },
                )
                await server_queue.consume(
                    self.server_specific_callback,
                )

        except Exception as e:
            logging.error("Error connecting to RabbitMQ: %s", e)
            raise
        else:
            logging.info("Consumer connected to RabbitMQ")

    async def reconnect_callback(self, connection: AbstractConnection) -> None:
        logging.info("Reconnecting to RabbitMQ...")
        self.connection = connection
        self.channel = await connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        self.queue = await self.channel.declare_queue(
            name=MODEL,
            durable=True,
            arguments={
                "x-expires": settings.RPC_QUEUE_EXPIRATION,
                "x-message-ttl": settings.RPC_MESSAGE_EXPIRATION,
                "x-max-priority": settings.RPC_MAX_PRIORITY,
            },
        )
        await self.queue.consume(
            self.on_message_callback,
        )
        logging.info("Reconnected to RabbitMQ")

    async def close(self) -> None:
        logging.debug("Closing RPC connection...")
        if await self.check_connection():
            try:
                await self.connection.close()
            except Exception as e:
                logging.error("Could not close RPC connection: %s", e)
            else:
                self.connection = None
                self.channel = None
                logging.info("RPC disconnected")

    async def on_message_callback(self, message: AbstractIncomingMessage):
        logging.debug("Message consumed on queue %s", MODEL)

        try:
            vllm_server, performance_indicator = self.strategy.choose_server()
            priority = self.priority_handler.apply_priority(message.priority)
            if not self.quality_of_service_policy.apply_policy(
                performance_indicator,
                self.current_parallel_requests[vllm_server],
                vllm_server.max_parallel_requests,
                message,
            ):
                return
            llm_params = {"llmUrl": vllm_server.url, "llmToken": vllm_server.token}
            if priority is not None and isinstance(priority, int):
                llm_params["priority"] = priority
        except ServerNotFound:
            vllm_server = None
            llm_params = {"llmUrl": "None", "llmToken": "None"}
        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(llm_params).encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to,
            )
            await message.ack()
            if vllm_server:
                self.current_parallel_requests[vllm_server] += 1
            logging.info("LLM URL for model %s sent to API", MODEL)
        except Exception as e:
            logging.error("An error occurred while publishing message: %s", e)
            raise

    async def on_completion_callback(self, message: AbstractIncomingMessage):
        try:
            data = json.loads(message.body.decode("utf-8"))
            logging.debug(
                "Completion received for message ID: %s, completed_at: %s",
                data.get("message_id"),
                data.get("completed_at"),
            )

            used_server = None
            server_url = data.get("server")
            for server in settings.VLLM_SERVERS:
                if server.url == server_url:
                    used_server = server

            if used_server:
                self.current_parallel_requests[used_server] = max(
                    self.current_parallel_requests[used_server] - 1, 0
                )
            logging.debug(
                "self.current_parallel_requests = %s", self.current_parallel_requests
            )
            await message.ack()
        except Exception as e:
            logging.error("Error processing completion message: %s", e)

    def choose_among_duplicates(
        self, duplicates: List[VLLMServer]
    ) -> tuple[VLLMServer, float | None]:
        scores = {}
        for server in duplicates:
            scores[server] = self.strategy.get_server_score(server.url)
            if scores[server] == -1:
                return server, -1
        has_none = any(value is None for value in scores.values())
        if has_none:
            return random.choice(list(scores.keys())), None
        min_value = min(scores.values())
        return (
            random.choice([k for k, v in scores.items() if v == min_value]),
            min_value,
        )

    async def server_specific_callback(self, message: AbstractIncomingMessage):
        try:
            data = json.loads(message.body.decode("utf-8"))
            routing_mode = data.get("routing_mode")
            organization = data.get("organization")
            priority = self.priority_handler.apply_priority(message.priority)

            matching_servers = [
                server
                for server in settings.VLLM_SERVERS
                if server.organization == organization
            ]
            target_server, score = self.choose_among_duplicates(matching_servers)

            target_requeue = None
            if routing_mode == "private-first":
                target_requeue = self.queue
            elif routing_mode != "private-only":
                raise UnknownLocalPriorityModel(routing_mode)

            if not self.quality_of_service_policy.apply_policy(
                score,
                self.current_parallel_requests[target_server],
                target_server.max_parallel_requests,
                message,
                target_requeue,
                self.channel.default_exchange,
            ):
                return

            llm_params = {"llmUrl": target_server.url, "llmToken": target_server.token}
            if priority is not None and isinstance(priority, int):
                llm_params["priority"] = priority

            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(llm_params).encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    correlation_id=str(message.correlation_id),
                ),
                routing_key=message.reply_to,
            )
            await message.ack()
            self.current_parallel_requests[target_server] += 1
            logging.info("LLM URL for model %s sent to API", MODEL)
        except Exception as e:
            logging.error("Error processing server specific message: %s", e)

    async def check_connection(self) -> bool:
        if self.connection and self.channel:
            if not self.connection.is_closed and not self.channel.is_closed:
                return True
        return False
