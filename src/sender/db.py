import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from src.sender.settings import Settings


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_url = settings.DATABASE_URL

        self.engine = create_engine(self.db_url, echo=False)
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1;"))
                logging.info("Database connection successful! 🎉")

        except OperationalError as e:
            logging.error("Error: Could not connect to the database. Details: %s", e)
            raise e
        except Exception as e:
            logging.error("An unexpected error occurred: %s", e)
            raise e

        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def close(self):
        self.engine.dispose()
