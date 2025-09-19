from sqlalchemy import Column, Enum, Integer, String

from src.sender.entities.base import Base


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
    default_routing_mode = Column(
        Enum("any", "private-first", "private-only", native_enum=False),
        nullable=False,
        default="any",
    )
