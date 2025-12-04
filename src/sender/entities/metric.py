from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String

from src.sender.entities.base import Base


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(length=255), ForeignKey("users.name"), nullable=False)
    request_date = Column(DateTime)
    sent_to_llm_date = Column(DateTime)
    response_date = Column(DateTime)
    model = Column(String(length=255))
    server = Column(String(length=255))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    strategy = Column(String(length=255))
    requeue_count = Column(Integer)
    max_parallel_requests = Column(Integer, nullable=True)
    current_parallel_requests = Column(Integer, nullable=True)
    priority = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    routing_mode = Column(
        Enum("any", "private-first", "private-only", native_enum=False)
    )
