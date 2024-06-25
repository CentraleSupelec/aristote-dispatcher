from pydantic_settings import BaseSettings
import logging

class Settings(BaseSettings):
    LOG_LEVEL: int = logging.INFO
    MODEL: str = None
    AVG_TOKEN_THRESHOLD: int = 7
    NB_USER_THRESHOLD: int = 10
    X_MAX_PRIORITY: int = 5
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    POD_NAME: str = "localhost"
    SERVICE_NAME: str = ""
    TARGET_PORT: int = 8080

    @property
    def RABBITMQ_URL(self):
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @property
    def LLM_URL(self):
        return f"http://{self.POD_NAME}.{self.SERVICE_NAME}:{self.TARGET_PORT}"