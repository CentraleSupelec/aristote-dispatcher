from dataclasses import dataclass


@dataclass(frozen=True)
class VLLMServer:
    url: str
    token: str
