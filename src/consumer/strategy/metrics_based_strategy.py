from abc import abstractmethod
from typing import List

from src.consumer.strategy.metrics_tracker import MetricsTracker
from src.consumer.strategy.server_selection_strategy import ServerSelectionStrategy
from src.consumer.vllm_server import VLLMServer


class MetricsBasedStrategy(ServerSelectionStrategy):
    """
    Strategy interface for strategies that depend on server metrics.
    """

    def __init__(self, servers: List[VLLMServer], tracker: MetricsTracker) -> None:
        super().__init__(servers)
        self._tracker = tracker

    @property
    @abstractmethod
    def tracker(self) -> MetricsTracker:
        pass

    @classmethod
    @abstractmethod
    async def create(
        cls,
        servers: List[VLLMServer],
        refresh_rate: int,
        refresh_count_per_window: int,
    ) -> "MetricsBasedStrategy":
        """
        Subclasses must implement this async method to handle async setup
        and return an instance of the strategy.
        Should create a MetricsTracker instance and pass it to the constructor
        """

    async def update_servers(self, servers: List[VLLMServer]) -> None:
        if servers != self.servers:
            await self.tracker.stop_monitor()
            await super().update_servers(servers)
            self.tracker.update_urls([server.url for server in servers])
            await self.tracker.monitor()
