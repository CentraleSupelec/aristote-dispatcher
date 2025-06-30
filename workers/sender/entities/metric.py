from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from .base import Base


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String, ForeignKey("users.name"), nullable=False)
    request_date = Column(DateTime)
    sent_to_llm_date = Column(DateTime)
    response_date = Column(DateTime)
    model = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
