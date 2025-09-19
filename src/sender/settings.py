import json
import logging
from typing import Dict, List, Literal

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
    PROXY_CLIENT_REQUEST_TIMEOUT: int = Field(default=600)

    DB_TYPE: Literal["mysql", "postgresql"] = Field(default="mysql")
    DB_HOST: str = Field()
    DB_PORT: int = Field(default=3306)
    DB_USER: str = Field()
    DB_PASSWORD: str = Field()
    DB_DATABASE: str = Field()

    DEFAULT_MODEL_HOST_MAPPING: str = Field(default=None, alias="MODEL_HOST_MAPPING")

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

    @property
    def MODEL_HOST_MAPPING(self) -> Dict[str, List[str]]:
        try:
            mapping = json.loads(self.DEFAULT_MODEL_HOST_MAPPING)
            if not isinstance(mapping, dict):
                raise ValueError("MODEL_HOST_MAPPING must be a JSON object")
            for _, v in mapping.items():
                if not isinstance(v, list) or not all(isinstance(i, str) for i in v):
                    raise ValueError(
                        "Each value in MODEL_HOST_MAPPING must be a list of strings"
                    )
            return mapping
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format for MODEL_HOST_MAPPING") from e
