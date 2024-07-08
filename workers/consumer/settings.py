from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import logging


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
    DEFAULT_LLM_URL: Optional[str] = Field(alias="LLM_URL", default=None)

    @property
    def LLM_URL(self):

        if self.DEFAULT_LLM_URL:
            return self.DEFAULT_LLM_URL
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
