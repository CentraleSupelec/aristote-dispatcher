from pydantic_settings import BaseSettings
from pydantic import Field
import logging

class Settings(BaseSettings):
    LOG_LEVEL: int = Field(default=logging.INFO, env='LOG_LEVEL')
    MODEL: str = Field(default=None, env='MODEL')
    AVG_TOKEN_THRESHOLD: int = Field(default=7, env='AVG_TOKEN_THRESHOLD')
    NB_USER_THRESHOLD: int = Field(default=10, env='NB_USER_THRESHOLD')
    X_MAX_PRIORITY: int = Field(default=5, env='X_MAX_PRIORITY')
    RABBITMQ_USER: str = Field(default="guest", env='RABBITMQ_USER')
    RABBITMQ_PASSWORD: str = Field(default="guest", env='RABBITMQ_PASSWORD')
    RABBITMQ_HOST: str = Field(default="localhost", env='RABBITMQ_HOST')
    RABBITMQ_PORT: int = Field(default=5672, env='RABBITMQ_PORT')
    POD_NAME: str = Field(default="localhost", env='POD_NAME')
    SERVICE_NAME: str = Field(default="", env='SERVICE_NAME')
    TARGET_PORT: int = Field(default=8080, env='TARGET_PORT')
    LLM_URL: str = Field(default=f"http://{POD_NAME}.{SERVICE_NAME}:{TARGET_PORT}", env='LLM_URL')

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"