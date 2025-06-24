from ._base_priority_handler import BasePriorityHandler


class VllmPriorityHandler(BasePriorityHandler):
    def apply_priority(self, current_priority) -> None | int:
        return max(self.best_priority - current_priority, 0)
