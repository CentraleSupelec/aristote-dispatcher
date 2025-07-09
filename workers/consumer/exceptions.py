class ModelMetricsUpdateException(Exception):
    def __init__(self, retry, vllm_url):
        message = f"Failed to update model metrics after {retry} attempts at {vllm_url}"
        super().__init__(message)


class VllmNotReadyException(Exception):
    def __init__(self, seconds):
        message = f"vllm is not ready after {seconds}s"
        super().__init__(message)


class ServerNotFound(Exception):
    def __init__(self):
        message = "No server found"
        super().__init__(message)


class UnknownStrategy(Exception):
    def __init__(self, passed_strategy):
        message = f'"{passed_strategy}" not recognized; strategy must be either round-robin or least-busy'
        super().__init__(message)


class UnknownPriorityHandler(Exception):
    def __init__(self, priority_handler):
        message = f'"{priority_handler}" not recognized; priority handler must be either "ignore" or "vllm"'
        super().__init__(message)


class PercentileComputationError(Exception):
    def __init__(self, percentile, histogram):
        message = (
            f"Couldn't find {100*percentile}th percentile for histogram: {histogram}"
        )
        super().__init__(message)


class UnknownQOSPolicy(Exception):
    def __init__(self, passed_policy):
        message = f'"{passed_policy} not recognized; policy must either be "warning-log" or "requeue"'
        super().__init__(message)
