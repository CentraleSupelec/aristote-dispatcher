from abc import ABC, abstractmethod


class BasePriorityHandler(ABC):
    def __init__(self, best_priority: int):
        self.best_priority = best_priority

    @abstractmethod
    def apply_priority(self, current_priority: int) -> None | int:
        pass
