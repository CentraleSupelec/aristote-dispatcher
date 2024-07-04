import asyncio
import logging
import re

from httpx import AsyncClient
from math import inf
from settings import settings


LLM_URL = settings.LLM_URL

DEFAULT_RETRY = 5


async def update_metrics():

    async with AsyncClient(base_url=LLM_URL) as http_client:
        response = await http_client.get("/metrics/")
        response.raise_for_status()

    content = response.text

    line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
    num_requests_running = r"^vllm:num_requests_running.*$"

    tokens_per_second = float(
        re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_nb_users = float(
        re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_avg_token = (
        tokens_per_second / current_nb_users if current_nb_users else inf
    )

    logging.debug(f" > [Metrics] Tokens per second: {tokens_per_second}")
    logging.debug(f" > [Metrics] Running requests: {current_nb_users}")
    logging.debug(f" > [Metrics] Average token per user: {current_avg_token}")

    return current_avg_token, current_nb_users


async def try_update_metrics(retry: int = DEFAULT_RETRY):
    for attempt in range(retry):
        try:
            return await update_metrics()
        except Exception as e:
            logging.error(
                f"Attempt {attempt+1}/{retry} to update model metrics failed: {e}"
            )
            await asyncio.sleep(attempt)
    else:
        logging.error(f"Failed to update model metrics atfer {retry} attempts")
        raise Exception(f"Failed to update model metrics atfer {retry} attempts")
