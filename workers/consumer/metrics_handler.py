import asyncio
import logging
import re

from httpx import AsyncClient
from math import inf
from settings import settings


LLM_URL = settings.LLM_URL

DEFAULT_RETRY = 10


class MetricsHandler:
    def __init__(self):
        self.current_avg_token = inf
        self.current_nb_users = 0

    async def get_metrics(self):
        await self.try_update_metrics()
        return self.current_avg_token, self.current_nb_users

    async def update_metrics(self):
        async with AsyncClient(base_url=LLM_URL) as http_client:
            try:
                response = await http_client.get("/metrics/")
                response.raise_for_status()
            except Exception as e:
                logging.error(f"Failed to update model metrics: {e}")
                raise
        
        content = response.text

        line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
        num_requests_running = r"^vllm:num_requests_running.*$"

        tokens_per_second = float(re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1])
        self.current_nb_users = float(re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1])
        self.current_avg_token = tokens_per_second/self.current_nb_users if self.current_nb_users else inf

        logging.debug(f" > [Metrics] Tokens per second: {tokens_per_second}")
        logging.debug(f" > [Metrics] Running requests: {self.current_nb_users}")
        logging.debug(f" > [Metrics] Average token per user: {self.current_avg_token}")

    async def try_update_metrics(self, retry: int = DEFAULT_RETRY):
        for attempt in range(retry):
            try:
                await self.update_metrics()
                return
            except Exception:
                logging.debug(f"Attempt {attempt+1}/{retry} to update model metrics failed")
                await asyncio.sleep(attempt)
        logging.error(f"Failed to update model metrics atfer {retry} attempts")
        raise Exception(f"Failed to update model metrics atfer {retry} attempts")


metrics_handler = MetricsHandler()