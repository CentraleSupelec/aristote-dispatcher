from pydantic_settings import BaseSettings
from pydantic import Field
import logging


class Settings(BaseSettings):
    LOG_LEVEL: int = Field(default=logging.INFO, env='LOG_LEVEL')
    RABBITMQ_USER: str = Field(default="guest", env='RABBITMQ_USER')
    RABBITMQ_PASSWORD: str = Field(default="guest", env='RABBITMQ_PASSWORD')
    RABBITMQ_HOST: str = Field(default="localhost", env='RABBITMQ_HOST')
    RABBITMQ_PORT: int = Field(default=5672, env='RABBITMQ_PORT')
    RABBITMQ_MANAGEMENT_PORT : int = Field(default=15672, env='RABBITMQ_MANAGEMENT_PORT')

    DB_TYPE: str = Field(default="mysql", env="DB_TYPE")
    DB_HOST: str = Field(env="DB_HOST")
    DB_PORT: int = Field(default=3306 if DB_TYPE == "mysql" else 5432, env="DB_PORT")
    DB_USER: str = Field(env="DB_USER")
    DB_PASSWORD: str = Field(env="DB_PASSWORD")
    DB_DATABASE: str = Field(env="DB_DATABASE")

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @property
    def RABBITMQ_MANAGEMENT_URL(self):
        return f"http://{self.RABBITMQ_HOST}:{self.RABBITMQ_MANAGEMENT_PORT}"
