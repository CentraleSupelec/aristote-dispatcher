import asyncio
import logging
import re

from httpx import AsyncClient
from math import inf
from settings import settings, VLLMServer
from typing import Tuple, List

DEFAULT_RETRY = 5

# Consumer will wait for MAX_INITIAL_METRICS_RETRIES*INITIAL_METRCIS_WAIT seconds
# Before crashing if vllm is not ready
MAX_INITIAL_METRICS_RETRIES = settings.MAX_VLLM_CONNECTION_ATTEMPTS
INITIAL_METRCIS_WAIT = settings.INITIAL_METRCIS_WAIT


async def update_metrics(vllm_server: VLLMServer) -> Tuple[float, float, float, VLLMServer]:

    async with AsyncClient(base_url=vllm_server.url) as http_client:
        response = await http_client.get("/metrics/")
        response.raise_for_status()

    content = response.text

    line_pattern = r"^vllm:avg_generation_throughput_toks_per_s.*$"
    num_requests_running = r"^vllm:num_requests_running.*$"
    num_requests_waiting = r"^vllm:num_requests_waiting.*$"

    tokens_per_second = float(
        re.search(line_pattern, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_nb_users = float(
        re.search(num_requests_running, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_nb_requests_in_queue = float(
        re.search(num_requests_waiting, content, re.MULTILINE).group(0).split(" ")[1]
    )
    current_avg_token = (
        tokens_per_second / current_nb_users if current_nb_users else inf
    )

    logging.debug(f" > [Metrics] Tokens per second: {tokens_per_second}")
    logging.debug(f" > [Metrics] Running requests: {current_nb_users}")
    logging.debug(f" > [Metrics] Waiting requests: {current_nb_requests_in_queue}")
    logging.debug(f" > [Metrics] Average token per user: {current_avg_token}")

    return current_avg_token, current_nb_users, current_nb_requests_in_queue, vllm_server

async def try_update_metrics(vllm_server: VLLMServer, retry: int = DEFAULT_RETRY) -> Tuple[float, float, float, VLLMServer]:
    for attempt in range(retry):
        try:
            return await update_metrics(vllm_server)
        except Exception as e:
            logging.error(
                f"Attempt {attempt+1}/{retry} to update model metrics at {vllm_server.url} failed: {e}"
            )
            await asyncio.sleep(attempt)
    else:
        logging.error(f"Failed to update model metrics atfer {retry} attempts at {vllm_server.url}")
        raise Exception(f"Failed to update model metrics atfer {retry} attempts at {vllm_server.url}")
    
async def stream_update_metrics(vllm_servers: List[VLLMServer], retry: int = DEFAULT_RETRY):
    tasks = [asyncio.create_task(try_update_metrics(server, retry)) for server in vllm_servers]

    for task in asyncio.as_completed(tasks):
        try:
            current_avg_token, current_nb_users, current_nb_requests_in_queue, vllm_server = await task

            logging.info(f"Received metrics from {vllm_server.url}: avg_token={current_avg_token}, users={current_nb_users}, queue={current_nb_requests_in_queue}")

            yield current_avg_token, current_nb_users, current_nb_requests_in_queue, vllm_server

        except Exception as e:
            logging.error(f"Failed to fetch metrics from a server: {e}")

async def wait_for_vllms(vllm_servers: List[VLLMServer]) -> None:
    tasks = {asyncio.create_task(wait_for_vllm(vllm_server)): vllm_server for vllm_server in vllm_servers}

    done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        if task.exception() is None:
            logging.info(f"Server {tasks[task]} is ready.")
            break

    for task in pending:
        task.cancel()

async def wait_for_vllm(vllm_server: VLLMServer) -> None:
    for i in range(MAX_INITIAL_METRICS_RETRIES):
        try:
            await update_metrics(vllm_server)
            logging.info("vllm is ready")
            break
        except Exception as e:
            logging.error(
                f"Waiting for vllm to be ready ({i+1}/{MAX_INITIAL_METRICS_RETRIES}): {e}"
            )
            await asyncio.sleep(INITIAL_METRCIS_WAIT)
    else:
        raise Exception(f"vllm is not ready after {INITIAL_METRCIS_WAIT*MAX_INITIAL_METRICS_RETRIES}s")
