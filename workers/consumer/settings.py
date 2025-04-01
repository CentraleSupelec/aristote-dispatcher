import json
import logging
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

from .vllm_server import VLLMServer


class Settings(BaseSettings):
    AVG_TOKEN_THRESHOLD: int = Field(default=7)
    LOG_LEVEL: int = Field(default=logging.INFO)
    MODEL: str = Field(default=None)
    NB_USER_THRESHOLD: int = Field(default=10)
    RABBITMQ_HOST: str = Field(default="rabbitmq")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PORT: int = Field(default=5672)
    RPC_QUEUE_EXPIRATION: int = Field(default=30000)
    USE_PROBES: int = Field(default=0)
    PROBE_PORT: int = Field(default=8081)
    DEFAULT_VLLM_SERVERS: str = Field(default=None, alias="VLLM_SERVERS")
    MAX_VLLM_CONNECTION_ATTEMPTS: int = Field(default=100)
    INITIAL_METRCIS_WAIT: int = Field(default=5)
    NB_REQUESTS_IN_QUEUE_THRESHOLD: int = Field(default=5)
    ROUTING_STRATEGY: Literal["less-busy", "round-robin"] = Field(default=None)

    @property
    def VLLM_SERVERS(self):  # pylint: disable=invalid-name

        if self.DEFAULT_VLLM_SERVERS:
            try:
                servers = json.loads(self.DEFAULT_VLLM_SERVERS)
                return [
                    VLLMServer(url=url, token=token if token else None)
                    for url, token in servers.items()
                ]
            except json.JSONDecodeError as e:
                raise ValueError("Invalid JSON format for VLLM_SERVERS") from e
        else:
            raise ValueError("VLLM_SERVERS env variable is required")

    @property
    def RABBITMQ_URL(self):  # pylint: disable=invalid-name
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"


settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)
