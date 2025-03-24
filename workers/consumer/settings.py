from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from vllm_server import VLLMServer
import logging
import json


class Settings(BaseSettings):
    AVG_TOKEN_THRESHOLD: int = Field(default=7)
    LOG_LEVEL: int = Field(default=logging.INFO)
    MODEL: str = Field(default=None)
    NB_USER_THRESHOLD: int = Field(default=10)
    POD_NAME: Optional[str] = Field(default=None)
    RABBITMQ_HOST: str = Field(default="localhost")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PORT: int = Field(default=5672)
    RPC_RECONNECT_ATTEMPTS: int = Field(default=10)
    RPC_QUEUE_EXPIRATION: int = Field(default=30000)
    SERVICE_NAME: Optional[str] = Field(default=None)
    TARGET_PORT: int = Field(default=8080)
    USE_PROBES: int = Field(default=0)
    PROBE_PORT: int = Field(default=8081)
    DEFAULT_VLLM_SERVERS: Optional[str] = Field(default=None, alias="VLLM_SERVERS")
    MAX_VLLM_CONNECTION_ATTEMPTS: int = Field(default=100)
    INITIAL_METRCIS_WAIT: int = Field(default=5)
    NB_REQUESTS_IN_QUEUE_THRESHOLD: int = Field(default=5)

    @property
    def VLLM_SERVERS(self):

        if self.DEFAULT_VLLM_SERVERS:
            try:
                servers = json.loads(self.DEFAULT_VLLM_SERVERS)
                vllm_servers = [
                    VLLMServer(
                        url=url,
                        token=server.get("token"),
                        exposes_metrics=server.get("exposes_metrics")
                    )
                    for url, server in servers.items()
                ]
                logging.debug(vllm_servers)
                return vllm_servers
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON format for VLLM_SERVERS")
        else:

            if not self.POD_NAME:
                raise ValueError("POD_NAME is not set")

            if not self.SERVICE_NAME:
                raise ValueError("SERVICE_NAME is not set")

            return f"http://{self.POD_NAME}.{self.SERVICE_NAME}:{self.TARGET_PORT}"

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"


settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)
