from abc import ABC, abstractmethod
from typing import List

from ..vllm_server import VLLMServer


class ServerSelectionStrategy(ABC):
    """
    Abstract base class for server selection strategies.
    """

    def __init__(self, servers: List[VLLMServer]) -> None:
        self.servers = servers

    @abstractmethod
    def choose_server(self) -> VLLMServer:
        pass

    async def monitor(self, interval: int = 10) -> None:
        pass

    async def stop_monitor(self) -> None:
        pass
