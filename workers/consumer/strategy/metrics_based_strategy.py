from abc import abstractmethod
from typing import List

from ..vllm_server import VLLMServer
from .metrics_tracker import MetricsTracker
from .server_selection_strategy import ServerSelectionStrategy


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
        threshold: float,
        refresh_rate: int,
        window_width: int,
    ) -> "MetricsBasedStrategy":
        """
        Subclasses must implement this async method to handle async setup
        and return an instance of the strategy.
        Should create a MetricsTracker instance and pass it to the constructor
        """
