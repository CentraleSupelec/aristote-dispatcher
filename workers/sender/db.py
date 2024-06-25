import os
import aiomysql
import asyncpg
import logging
from abc import ABC, abstractmethod

DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mysql")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306 if DATABASE_TYPE == "mysql" else 5432))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_DATABASE")

class Database(ABC):

    @abstractmethod
    async def create_connection_pool(self):
        return NotImplemented
    
    @abstractmethod
    async def execute(self, mysql_query: str, postgres_query: str, *args):
        return NotImplemented
    
    async def close(self):
        return NotImplemented
    
    @staticmethod
    async def init_database():
        if DATABASE_TYPE == "mysql":
            database = MySQLDatabase()
        elif DATABASE_TYPE == "postgresql":
            database = PostgreSQLDatabase()
        else:
            raise ValueError("Invalid database type")
        
        await database.create_connection_pool()

        return database
    

class MySQLDatabase(Database):
    pool: aiomysql.Pool | None = None

    async def create_connection_pool(self):
        self.pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME
        )
    
    async def execute(self, mysql_query: str, postgres_query: str, *args):

        if self.pool is None:
            raise ValueError("Pool is not initialized")

        logging.debug(" Executing query %r with args %r" % (mysql_query, args))

        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(mysql_query, args)
                result =  await cursor.fetchone()
                logging.debug(" [x] Result : %r" % result)

                return result
            
    async def close(self):
        if self.pool is not None:
           self.pool.close()
           await self.pool.wait_closed()
            


class PostgreSQLDatabase(Database):
    pool: asyncpg.Pool | None = None

    async def create_connection_pool(self):
        self.pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    
    async def execute(self, mysql_query: str, postgres_query: str, *args):

        if self.pool is None:
            raise ValueError("Pool is not initialized")
        
        logging.debug(" Executing query %r with args %r" % (postgres_query, args))

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchrow(postgres_query, *args)
                logging.debug(" [x] Result : %r" % result)

                return result
            
    async def close(self):
        if self.pool is not None:
            self.pool.close()


    
