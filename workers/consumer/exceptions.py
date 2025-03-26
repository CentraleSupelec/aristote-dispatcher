class ModelMetricsUpdateException(Exception):
    def __init__(self, retry, vllm_url):
        message = f"Failed to update model metrics after {retry} attempts at {vllm_url}"
        super().__init__(message)


class VllmNotReadyException(Exception):
    def __init__(self, seconds):
        message = f"vllm is not ready after {seconds}s"
        super().__init__(message)


class NoSuitableVllm(Exception):
    def __init__(self):
        message = "No suitable VLLM server found with good enough metrics"
        super().__init__(message)
