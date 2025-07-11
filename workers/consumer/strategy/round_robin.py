from typing import List

from ..exceptions import ServerNotFound
from ..vllm_server import VLLMServer
from .server_selection_strategy import ServerSelectionStrategy


class RoundRobin(ServerSelectionStrategy):  # pylint: disable=too-few-public-methods

    def __init__(self, servers: List[VLLMServer]) -> None:
        super().__init__(servers)
        self.round_robin_idx = 0

    async def update_servers(self, servers: List[VLLMServer]) -> None:
        self.round_robin_idx = 0
        await super().update_servers(servers)

    def choose_server(self) -> (VLLMServer, None):
        if self.servers:
            choice = self.servers[self.round_robin_idx]
            self.round_robin_idx = (self.round_robin_idx + 1) % len(self.servers)
            return choice, None
        raise ServerNotFound()
