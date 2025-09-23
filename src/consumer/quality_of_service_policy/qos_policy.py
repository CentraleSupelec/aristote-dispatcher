from abc import ABC, abstractmethod

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue


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
        exchange: AbstractExchange,
        message: AbstractIncomingMessage | None = None,
        target_requeue: AbstractQueue | None = None,
        delay: int | None = None,
    ) -> bool:
        pass
