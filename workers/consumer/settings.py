import json
import logging
from typing import List, Literal, Optional

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
    RPC_QUEUE_EXPIRATION: int = Field(default=30_000)  # 30s in milliseconds
    RPC_MESSAGE_EXPIRATION: int = Field(default=570_000)  # 9m30s in  milliseconds
    RPC_MAX_PRIORITY: int = Field(ge=1, default=5)
    USE_PROBES: int = Field(default=0)
    PROBE_PORT: int = Field(default=8081)
    DEFAULT_VLLM_SERVERS: str = Field(default=None, alias="VLLM_SERVERS")
    MAX_VLLM_CONNECTION_ATTEMPTS: int = Field(default=100)
    INITIAL_METRICS_WAIT: int = Field(default=5)
    ROUTING_STRATEGY: Literal["least-busy", "round-robin"] = Field(default=None)
    PRIORITY_HANDLER: Literal["ignore", "vllm"] = Field(default="ignore")
    BEST_PRIORITY: int = Field(default=5)
    TIME_TO_FIRST_TOKEN_THRESHOLD: Optional[float] = None
    METRICS_REFRESH_RATE: int = Field(ge=1, default=1)  # in seconds
    REFRESH_COUNT_PER_WINDOW: int = Field(ge=1, default=24)
    # A time window would then be of duration METRICS_REFRESH_RATE * REFRESH_COUNT_PER_WINDOW
    PING_REFRESH_RATE: int = Field(ge=1, default=30)  # in seconds
    QUALITY_OF_SERVICE_POLICY: Literal["warning-log", "requeue"] = Field(
        default="warning-log"
    )
    DEFAULT_MAX_PARALLEL_REQUESTS: int = Field(default=20)

    @property
    def VLLM_SERVERS(self) -> List[VLLMServer]:
        if not self.DEFAULT_VLLM_SERVERS:
            raise ValueError("VLLM_SERVERS env variable is required")

        try:
            raw_servers = json.loads(self.DEFAULT_VLLM_SERVERS)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format for VLLM_SERVERS") from e

        servers = []
        for url, config in raw_servers.items():
            if not isinstance(config, dict):
                raise ValueError(
                    f"Each VLLM server must be a JSON object, got {type(config)} at {url}"
                )

            servers.append(
                VLLMServer(
                    url=url,
                    token=config.get("token"),
                    organization=config["organization"],
                    max_parallel_requests=config.get(
                        "max_parallel_requests", self.DEFAULT_MAX_PARALLEL_REQUESTS
                    ),
                )
            )
        return servers

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


settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
)
