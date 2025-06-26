from ._base_priority_handler import BasePriorityHandler


class IgnorePriorityHandler(BasePriorityHandler):
    def apply_priority(self, current_priority: int) -> None | int:
        return None
