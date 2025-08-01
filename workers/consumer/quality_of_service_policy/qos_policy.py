from abc import ABC, abstractmethod

from aio_pika import Exchange
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue


class QualityOfServiceBasePolicy(ABC):  # pylint: disable=too-few-public-methods
    """
    Abstract base class for qos policies
    """

    def __init__(self, performance_threshold: float | None) -> None:
        self.performance_threshold = performance_threshold

    @abstractmethod
    def apply_policy(
        self,
        performance_indicator: float | None,
        current_parallel_requests: int,
        max_parallel_requests: int,
        message: AbstractIncomingMessage | None = None,
        target_requeue: AbstractQueue | None = None,
        exchange: Exchange | None = None,
    ) -> bool:
        pass
