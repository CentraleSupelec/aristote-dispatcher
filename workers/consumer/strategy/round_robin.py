from typing import List

from ..vllm_server import VLLMServer
from .server_selection_strategy import ServerSelectionStrategy


class RoundRobin(ServerSelectionStrategy):

    def __init__(self, servers: List[VLLMServer]) -> None:
        super().__init__(servers)
        self.round_robin_idx = 0

    def choose_server(self) -> VLLMServer:
        choice = self.servers[self.round_robin_idx]
        self.round_robin_idx = (self.round_robin_idx + 1) % len(self.servers)
        return choice
