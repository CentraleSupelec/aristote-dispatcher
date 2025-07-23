import logging
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: int = Field(default=logging.INFO)
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_HOST: str = Field(default="rabbitmq")
    RABBITMQ_PORT: int = Field(default=5672)
    RABBITMQ_MANAGEMENT_PORT: int = Field(default=15672)
    MESSAGE_TIMEOUT: int = Field(default=570)  # 9m30s in seconds
    REQUEST_TIMEOUT: int = Field(default=600)

    DB_TYPE: Literal["mysql", "postgresql"] = Field(default="mysql")
    DB_HOST: str = Field()
    DB_PORT: int = Field(default=3306)
    DB_USER: str = Field()
    DB_PASSWORD: str = Field()
    DB_DATABASE: str = Field()

    ARTIFICIAL_TIMEOUT: int = Field(default=0)

    @model_validator(mode="after")
    def check_required_fields(self):
        missing_fields = [
            field
            for field in ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_DATABASE"]
            if not getattr(self, field, None)
        ]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return self

    @property
    def RABBITMQ_URL(self):  # pylint: disable=invalid-name
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @property
    def RABBITMQ_MANAGEMENT_URL(self):  # pylint: disable=invalid-name
        return f"http://{self.RABBITMQ_HOST}:{self.RABBITMQ_MANAGEMENT_PORT}"
