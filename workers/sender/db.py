from entities import Base
from settings import Settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings

        if settings.DB_TYPE == "mysql":
            self.db_url = (
                f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
                f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DATABASE}"
            )
        elif settings.DB_TYPE == "postgresql":
            self.db_url = (
                f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@"
                f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DATABASE}"
            )
        else:
            raise ValueError(f"Unsupported DB_TYPE: {settings.DB_TYPE}")

        self.engine = create_engine(self.db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def close(self):
        self.engine.dispose()
