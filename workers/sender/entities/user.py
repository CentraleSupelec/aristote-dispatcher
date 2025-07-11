from sqlalchemy import Column, Integer, String

from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)
    organization = Column(String, nullable=True)
    email = Column(String, nullable=True)
    priority = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    client_type = Column(String)
