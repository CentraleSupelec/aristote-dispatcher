from pydantic_settings import BaseSettings
from pydantic import Field
import logging


class Settings(BaseSettings):
    AVG_TOKEN_THRESHOLD: int = Field(default=7, env='AVG_TOKEN_THRESHOLD')
    LOG_LEVEL: int = Field(default=logging.INFO, env='LOG_LEVEL')
    MODEL: str = Field(default=None, env='MODEL')
    NB_USER_THRESHOLD: int = Field(default=10, env='NB_USER_THRESHOLD')
    POD_NAME: str = Field(default="localhost", env='POD_NAME')
    RABBITMQ_HOST: str = Field(default="localhost", env='RABBITMQ_HOST')
    RABBITMQ_PASSWORD: str = Field(default="guest", env='RABBITMQ_PASSWORD')
    RABBITMQ_USER: str = Field(default="guest", env='RABBITMQ_USER')
    RABBITMQ_PORT: int = Field(default=5672, env='RABBITMQ_PORT')
    RPC_RECONNECT_ATTEMPTS: int = Field(default=10, env='RPC_RECONNECT_ATTEMPTS')
    SERVICE_NAME: str = Field(default="", env='SERVICE_NAME')
    TARGET_PORT: int = Field(default=8080, env='TARGET_PORT')
    USE_PROBES: int = Field(default=0, env='USE_PROBES')
    
    LLM_URL: str = Field(default=f"http://{POD_NAME}.{SERVICE_NAME}:{TARGET_PORT}", env='LLM_URL')

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"


settings = Settings()

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
