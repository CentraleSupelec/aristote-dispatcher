import asyncio
import logging
from typing import Dict, List

import aiohttp

from .histogram import Histogram


class MetricsTracker:
    # We can imagine different strategies based on different metrics
    # In this case, these patterns would be passed in the constructor
    time_to_first_token_pattern = r"^vllm:time_to_first_token_seconds_bucket.*$"

    def __init__(self, urls: List[str]) -> None:
        self.urls = urls
        # The whole monitoring process only cares about urls, not complete server object,
        # which are less handy to use as dictionnary keys (i.e to hash)
        self.time_to_first_token_last_histograms: Dict[str, Histogram] = {
            url: Histogram() for url in self.urls
        }
        self.time_to_first_token_diff_histograms: Dict[str, Histogram] = {
            url: Histogram() for url in self.urls
        }
        self.monitoring = False
        self._monitor_tasks = []

    @staticmethod
    async def fetch_metrics(session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(f"{url}/metrics") as response:
            response.raise_for_status()
            return await response.text()

    @staticmethod
    def update_histogram(
        new_histogram: Histogram, last_histogram: Histogram, diff_histogram: Histogram
    ):
        new_diff_histogram = Histogram()
        new_diff_histogram = new_histogram - last_histogram

        last_histogram.update(new_histogram)
        diff_histogram.update(new_diff_histogram)

    async def update_all_metrics_for_server(
        self, session: aiohttp.ClientSession, url: str
    ) -> None:
        """Fetch metrics once and update histograms for different patterns."""
        content = await MetricsTracker.fetch_metrics(session, url)
        if not content:
            return

        new_histogram = Histogram.parse(
            content, MetricsTracker.time_to_first_token_pattern
        )
        MetricsTracker.update_histogram(
            new_histogram,
            self.time_to_first_token_last_histograms.setdefault(url, Histogram()),
            self.time_to_first_token_diff_histograms.setdefault(url, Histogram()),
        )

    async def _monitor_server(self, url: str, interval: int) -> None:
        async with aiohttp.ClientSession() as session:
            while self.monitoring:
                try:
                    await self.update_all_metrics_for_server(session, url)
                    logging.debug("Metrics updated for %s", url)
                    logging.debug(
                        "time-to-first-token histogram: %s",
                        self.time_to_first_token_diff_histograms[url],
                    )
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    logging.debug("Monitoring task cancelled for %s", url)
                    break
                # Since we only wait for one server to start consuming (cf metrics.py),
                # it is possible that some servers are not (yet) reachable,
                # which leads to aiohttp.ClientConnectorError
                except aiohttp.ClientConnectorError:
                    continue

    async def monitor(self, interval: int = 10) -> None:
        if self.monitoring:
            logging.debug("Monitoring is already running.")
            return

        self.monitoring = True
        self._monitor_tasks = [
            asyncio.create_task(self._monitor_server(url, interval))
            for url in self.urls
        ]
        logging.debug("Started monitoring for %s servers", len(self.urls))

    async def stop_monitor(self) -> None:
        if not self.monitoring:
            logging.debug("Monitoring is not running.")
            return

        self.monitoring = False
        for task in self._monitor_tasks:
            task.cancel()
        await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        logging.debug("Monitoring stopped for all servers.")
