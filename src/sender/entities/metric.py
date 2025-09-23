from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

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
