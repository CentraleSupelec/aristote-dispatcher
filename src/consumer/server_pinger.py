import asyncio
import logging
from typing import List

import aiohttp

from src.consumer.strategy.server_selection_strategy import ServerSelectionStrategy
from src.consumer.vllm_server import VLLMServer


class ServerPinger:

    def __init__(
        self,
        servers: List[VLLMServer],
        time_interval: int,
        strategy: ServerSelectionStrategy,
    ):
        self.servers_to_monitor = servers
        self.time_interval = time_interval
        self.strategy = strategy
        self.monitoring = False

    async def ping_server(
        self, session: aiohttp.ClientSession, server: VLLMServer
    ) -> bool:
        url = f"{server.url}/v1/models"
        headers = {}
        if server.token:
            headers["Authorization"] = f"Bearer {server.token}"
        try:
            async with session.get(url, headers=headers, timeout=5) as response:
                return 200 <= response.status < 300
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def _monitor_servers(self):
        async with aiohttp.ClientSession() as session:
            while self.monitoring:
                tasks = [
                    self.ping_server(session, server)
                    for server in self.servers_to_monitor
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                healthy_servers = [
                    server
                    for server, is_healthy in zip(self.servers_to_monitor, results)
                    if isinstance(is_healthy, bool) and is_healthy
                ]

                # Update the strategy with the current healthy servers
                if not healthy_servers:
                    logging.critical(
                        "NO HEALTHY SERVERS FOUND: user requests will not be dispatched !"
                    )
                await self.strategy.update_servers(healthy_servers)

                logging.debug(
                    "Updated server list: %d OK servers", len(healthy_servers)
                )
                await asyncio.sleep(self.time_interval)

    async def monitor(self) -> None:
        if self.monitoring:
            logging.debug("Health monitoring is already running.")
            return

        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_servers())
        logging.debug("Started batch health monitoring for servers")

    async def stop_monitor(self) -> None:
        if not self.monitoring:
            logging.debug("Health monitoring is not running.")
            return

        self.monitoring = False
        self._monitor_task.cancel()
        await asyncio.gather(self._monitor_task, return_exceptions=True)
        logging.debug("Health monitoring stopped.")
