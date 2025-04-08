from abc import ABC, abstractmethod
from typing import List

from ..vllm_server import VLLMServer


class ServerSelectionStrategy(ABC):  # pylint: disable=too-few-public-methods
    """
    Abstract base class for server selection strategies.
    """

    def __init__(self, servers: List[VLLMServer]) -> None:
        self.servers = servers

    @abstractmethod
    def choose_server(self) -> VLLMServer:
        pass
