import asyncio
import logging
import re
from math import inf
from time import time
from typing import List, Tuple

from httpx import AsyncClient

from .exceptions import ModelMetricsUpdateException, VllmNotReadyException
from .settings import settings
from .vllm_server import VLLMServer

DEFAULT_RETRY = 5

# Consumer will wait for MAX_INITIAL_METRICS_RETRIES*INITIAL_METRCIS_WAIT seconds
# Before crashing if vllm is not ready
MAX_INITIAL_METRICS_RETRIES = settings.MAX_VLLM_CONNECTION_ATTEMPTS
INITIAL_METRCIS_WAIT = settings.INITIAL_METRCIS_WAIT

async def ping_server(vllm_server: VLLMServer):
    async with AsyncClient(base_url=vllm_server.url) as http_client:
        response = await http_client.get("/metrics/")
        response.raise_for_status()

def tokens_per_s(tokens_total: float, last_generation_tokens_total: float, timestamp: float, last_update_timestamp: float):
    time_diff = timestamp - last_update_timestamp
    token_diff = tokens_total - last_generation_tokens_total
    if token_diff > 0:
        return token_diff / time_diff
    return 0.

async def update_metrics(
    vllm_server: VLLMServer, throughput_metrics: dict
) -> Tuple[float, float, float, VLLMServer]:

    async with AsyncClient(base_url=vllm_server.url) as http_client:
        response = await http_client.get("/metrics/")
        response.raise_for_status()

    content = response.text

    generation_tokens_total = r"^vllm:generation_tokens_total.*$"
    num_requests_running = r"^vllm:num_requests_running.*$"
    num_requests_waiting = r"^vllm:num_requests_waiting.*$"

    timestamp = time()
    tokens_total = float(
        re.search(generation_tokens_total, content, re.MULTILINE).group(0).split(" ")[1]
    )

    if throughput_metrics[vllm_server.url]["first_update"]:
        tokens_per_second = 0.
        throughput_metrics[vllm_server.url]["first_update"] = False
    else:
        last_timestamp = throughput_metrics[vllm_server.url]["last_update_timestamp"]
        last_tokens_total = throughput_metrics[vllm_server.url]["last_generation_tokens_total"]
        tokens_per_second = tokens_per_s(tokens_total, last_tokens_total, timestamp, last_timestamp)

    throughput_metrics[vllm_server.url]["last_generation_tokens_total"] = tokens_total
    throughput_metrics[vllm_server.url]["last_update_timestamp"] = timestamp

    current_nb_users = float(
        re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_nb_requests_in_queue = float(
        re.search(num_requests_waiting, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_avg_token = (
        tokens_per_second / current_nb_users if current_nb_users else inf
    )

    logging.debug(
        " > [Metrics for %s] Tokens per second: %s", vllm_server.url, tokens_per_second
    )
    logging.debug(
        " > [Metrics for %s] Running requests: %s", vllm_server.url, current_nb_users
    )
    logging.debug(
        " > [Metrics for %s] Waiting requests: %s",
        vllm_server.url,
        current_nb_requests_in_queue,
    )
    logging.debug(
        " > [Metrics for %s] Average token per user: %s",
        vllm_server.url,
        current_avg_token,
    )

    return (
        current_avg_token,
        current_nb_users,
        current_nb_requests_in_queue,
        vllm_server,
    )


async def try_update_metrics(
    vllm_server: VLLMServer, throughput_metrics: dict, retry: int = DEFAULT_RETRY
) -> Tuple[float, float, float, VLLMServer]:
    for attempt in range(retry):
        try:
            return await update_metrics(vllm_server, throughput_metrics)
        except Exception as e:
            logging.error(
                "Attempt %s to update model metrics at %s failed: %s",
                (attempt + 1) / retry,
                vllm_server.url,
                e,
            )
            await asyncio.sleep(attempt)
    logging.error(
        "Failed to update model metrics atfer %s attempts at %s", retry, vllm_server.url
    )
    raise ModelMetricsUpdateException(retry, vllm_server.url)


async def stream_update_metrics(
    vllm_servers: List[VLLMServer], throughput_metrics: dict, retry: int = DEFAULT_RETRY
):
    tasks = [
        asyncio.create_task(try_update_metrics(server, throughput_metrics, retry))
        for server in vllm_servers
    ]

    for task in asyncio.as_completed(tasks):
        try:
            (
                current_avg_token,
                current_nb_users,
                current_nb_requests_in_queue,
                vllm_server,
            ) = await task

            logging.info(
                "Received metrics from %s: avg_token=%s, users=%s, queue=%s",
                vllm_server.url,
                current_avg_token,
                current_nb_users,
                current_nb_requests_in_queue,
            )

            yield current_avg_token, current_nb_users, current_nb_requests_in_queue, vllm_server, tasks

        except ModelMetricsUpdateException as e:
            logging.error("Failed to fetch metrics from a server: %s", e)


async def wait_for_vllms(vllm_servers: List[VLLMServer]) -> None:
    tasks = {
        asyncio.create_task(wait_for_vllm(vllm_server)): vllm_server
        for vllm_server in vllm_servers
    }

    done, pending = await asyncio.wait(
        tasks.keys(), return_when=asyncio.FIRST_COMPLETED
    )

    for task in done:
        if task.exception() is None:
            logging.info("Server %s is ready.", tasks[task])
            break
    else:
        logging.error(
            "No vllm ready after %ss",
            INITIAL_METRCIS_WAIT * MAX_INITIAL_METRICS_RETRIES,
        )
        raise task.exception()

    for task in pending:
        task.cancel()


async def wait_for_vllm(vllm_server: VLLMServer) -> None:
    for i in range(MAX_INITIAL_METRICS_RETRIES):
        try:
            await ping_server(vllm_server)
            logging.info("vllm is ready")
            break
        except Exception as e:
            logging.error(
                "Waiting for vllm to be ready (%s/%s): %s",
                (i + 1), MAX_INITIAL_METRICS_RETRIES,
                e,
            )
            await asyncio.sleep(INITIAL_METRCIS_WAIT)
    else:
        raise VllmNotReadyException(INITIAL_METRCIS_WAIT * MAX_INITIAL_METRICS_RETRIES)
