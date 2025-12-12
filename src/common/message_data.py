from pydantic import BaseModel


class MessageData(BaseModel):
    llm_url: str | None = None
    llm_token: str | None = None
    llm_organization: str | None = None
    strategy: str
    requeue_count: int = 0
    max_parallel_requests: int
    current_parallel_requests: int | None = None
    forwarded_priority: int | None = None
    performance_score: float | None = None
