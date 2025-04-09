import json
import logging
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from .vllm_server import VLLMServer


class Settings(BaseSettings):
    LOG_LEVEL: int = Field(default=logging.INFO)
    MODEL: str = Field(default=None)
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
    ROUTING_STRATEGY: Literal["least-busy", "round-robin"] = Field(default=None)
    TIME_TO_FIRST_TOKEN_THRESHOLD: Optional[float] = None
    METRICS_REFRESH_RATE: Optional[float] = None
    METRICS_WINDOW_WIDTH: Optional[float] = None

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

    @model_validator(mode="after")
    def validate_threshold(self):
        if self.ROUTING_STRATEGY == "least-busy":
            if self.TIME_TO_FIRST_TOKEN_THRESHOLD is None:
                self.TIME_TO_FIRST_TOKEN_THRESHOLD = 0.1  # pylint: disable=invalid-name
        else:
            # Ignore threshold for round-robin
            self.TIME_TO_FIRST_TOKEN_THRESHOLD = None
        return self

    @model_validator(mode="after")
    def validate_refresh_rate(self):
        if self.ROUTING_STRATEGY == "least-busy":
            if self.METRICS_REFRESH_RATE is None:
                self.METRICS_REFRESH_RATE = 2  # pylint: disable=invalid-name
            if self.METRICS_WINDOW_WIDTH is None:
                self.METRICS_WINDOW_WIDTH = 10  # pylint: disable=invalid-name
            if self.METRICS_WINDOW_WIDTH % self.METRICS_REFRESH_RATE != 0:
                raise ValueError(
                    "METRICS_WINDOW_WIDTH must be a multiple of METRICS_REFRESH_RATE. "
                    f"Passed values: METRICS_WINDOW_WIDTH={self.METRICS_WINDOW_WIDTH}; "
                    f"METRICS_REFRESH_RATE={self.METRICS_REFRESH_RATE}"
                )
        else:
            # Ignore these metrics-related variables for strategies that do not rely on monitoring
            self.METRICS_REFRESH_RATE = None
            self.METRICS_WINDOW_WIDTH = None
        return self


settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)
