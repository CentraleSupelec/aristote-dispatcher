import logging
from abc import ABC, abstractmethod

import aiomysql
import asyncpg
from settings import Settings


class Database(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def create_connection_pool(self):
        return NotImplemented

    @abstractmethod
    async def execute(self, mysql_query: str, postgres_query: str, *args):
        return NotImplemented

    async def close(self):
        return NotImplemented

    @staticmethod
    async def init_database(settings: Settings):
        match settings.DB_TYPE:
            case "mysql":
                database = MySQLDatabase(settings)
            case "postgresql":
                database = PostgreSQLDatabase(settings)
            case _:
                raise ValueError(f"Invalid database type: {settings.DB_TYPE}")

        await database.create_connection_pool()

        return database


class MySQLDatabase(Database):
    pool: aiomysql.Pool | None = None

    async def create_connection_pool(self):
        self.pool = await aiomysql.create_pool(
            host=self.settings.DB_HOST,
            port=self.settings.DB_PORT,
            user=self.settings.DB_USER,
            password=self.settings.DB_PASSWORD,
            db=self.settings.DB_DATABASE,
        )

    async def execute(self, mysql_query: str, postgres_query: str, *args):
        if self.pool is None:
            raise ValueError("Pool is not initialized")

        logging.debug("Executing query %s with args %s", mysql_query, args)

        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:

                await cursor.execute(mysql_query, args)
                result = await cursor.fetchall()

                logging.debug(" [x] Result : %s", result)

                return result[0]

    async def close(self):
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()


class PostgreSQLDatabase(Database):
    pool: asyncpg.Pool | None = None

    async def create_connection_pool(self):
        self.pool = await asyncpg.create_pool(
            host=self.settings.DB_HOST,
            port=self.settings.DB_PORT,
            user=self.settings.DB_USER,
            password=self.settings.DB_PASSWORD,
            database=self.settings.DB_DATABASE,
        )

    async def execute(self, mysql_query: str, postgres_query: str, *args):
        if self.pool is None:
            raise ValueError("Pool is not initialized")

        logging.debug("Executing query %s with args %s", postgres_query, args)

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchrow(postgres_query, *args)
                logging.debug("Result : %s", result)

                return result

    async def close(self):
        if self.pool is not None:
            self.pool.close()
