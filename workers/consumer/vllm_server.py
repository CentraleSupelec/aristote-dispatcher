from dataclasses import dataclass


@dataclass(frozen=True, eq=True)
class VLLMServer:
    url: str
    token: str | None
    organization: str
    max_parallel_requests: int
