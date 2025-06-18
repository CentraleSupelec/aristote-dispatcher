import logging


class WarningLogPolicy:
    def __init__(self, performance_threshold: float) -> None:
        self.performance_threshold = performance_threshold

    def apply_policy(self, performance_indicator: float | None) -> None:
        if (
            isinstance(performance_indicator, float)
            or isinstance(performance_indicator, int)
        ) and performance_indicator > self.performance_threshold:
            logging.warning(
                "Performance indicator exceeds threshold (%s > %s)",
                performance_indicator,
                self.performance_threshold,
            )
        return None
