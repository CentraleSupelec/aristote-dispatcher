import asyncio
import logging
from typing import List

from httpx import AsyncClient

from .exceptions import VllmNotReadyException
from .settings import settings
from .vllm_server import VLLMServer

DEFAULT_RETRY = 5

# Consumer will wait for MAX_INITIAL_METRICS_RETRIES*INITIAL_METRICS_WAIT seconds
# Before crashing if vllm is not ready
MAX_INITIAL_METRICS_RETRIES = settings.MAX_VLLM_CONNECTION_ATTEMPTS
INITIAL_METRICS_WAIT = settings.INITIAL_METRICS_WAIT


async def ping_server(vllm_server: VLLMServer) -> None:
    async with AsyncClient(base_url=vllm_server.url) as http_client:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if vllm_server.token:
            headers["Authorization"] = f"Bearer {vllm_server.token}"
        response = await http_client.get("/v1/models", headers=headers)
        response.raise_for_status()


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
            logging.info("Server %s is ready.", tasks[task].url)
            break
    else:
        logging.error(
            "No vllm ready after %ss",
            INITIAL_METRICS_WAIT * MAX_INITIAL_METRICS_RETRIES,
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
                (i + 1),
                MAX_INITIAL_METRICS_RETRIES,
                e,
            )
            await asyncio.sleep(INITIAL_METRICS_WAIT)
    else:
        raise VllmNotReadyException(INITIAL_METRICS_WAIT * MAX_INITIAL_METRICS_RETRIES)
