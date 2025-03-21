import logging

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: int = Field(default=logging.INFO)
    RABBITMQ_USER: str = Field(default="guest")
    RABBITMQ_PASSWORD: str = Field(default="guest")
    RABBITMQ_HOST: str = Field(default="rabbitmq")
    RABBITMQ_PORT: int = Field(default=5672)
    RABBITMQ_MANAGEMENT_PORT: int = Field(default=15672)

    DB_TYPE: str = Field(default="mysql")
    DB_HOST: str = Field()
    DB_PORT: int = Field(default=3306 if DB_TYPE == "mysql" else 5432)
    DB_USER: str = Field()
    DB_PASSWORD: str = Field()
    DB_DATABASE: str = Field()

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @property
    def RABBITMQ_MANAGEMENT_URL(self):
        return f"http://{self.RABBITMQ_HOST}:{self.RABBITMQ_MANAGEMENT_PORT}"
