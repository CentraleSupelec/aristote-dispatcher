import asyncio
import logging
import re
from math import inf
from typing import List

import aiohttp

from ..vllm_server import VLLMServer
from .server_selection_strategy import ServerSelectionStrategy


def get_percentile(histogram: dict, percentile: float = 0.95) -> tuple[int, float]:
    """
    histogram has the following shape:
    {
        0.3: 0.0,
        0.5: 1.0,
        0.8: 4.0,
        ...
        inf: <total number of requests>
    }

    sorted_buckets then has the following shape:
    [
        (0.3, 0.0), (0.5, 1.0), (0.8, 4.0), ...
    ]
    """
    sorted_buckets = sorted(histogram.items())
    total_requests = sorted_buckets[-1][1]
    percentile_count = percentile * total_requests
    for i, (bucket, count) in enumerate(sorted_buckets):
        if count >= percentile_count:
            return (i, bucket)
    return None
    # Should never be reached, since count holds total_requests during last iteration,
    # which will always be bigger than percentile*total_requests for percentile<1


def business_score(
    e2e_bucket: tuple[int, float], tft_bucket: tuple[int, float]
) -> float:
    """
    both buckets have the shape (bucket_index, bucket_value)
    as returned by the get_percentile function
    """
    # TODO: define a score based on e2e time and time to first token time
    return 0.0


def least_busy(scores: dict) -> str:
    """
    scores is a dict of shape {url: score} for each server
    """
    return min(scores, key=lambda x: scores[x])


class LeastBusy(ServerSelectionStrategy):
    e2e_latency_pattern = r"^vllm:e2e_request_latency_seconds_bucket.*$"
    time_to_first_token_pattern = r"^vllm:time_to_first_token_seconds_bucket.*$"
    bucket_pattern = r'le="([\d+.inf]+)".*? (\d+\.\d+)'

    def __init__(self, servers: List[VLLMServer]) -> None:
        super().__init__(servers)
        self.urls = [server.url for server in servers]
        # The whole monitoring process only cares about urls, not complete server object,
        # which are less handy to use as dictionnary keys (i.e to hash)
        self.e2e_latency_last_histograms = {url: {} for url in self.urls}
        self.e2e_latency_diff_histograms = {url: {} for url in self.urls}
        self.time_to_first_token_last_histograms = {url: {} for url in self.urls}
        self.time_to_first_token_diff_histograms = {url: {} for url in self.urls}
        self.monitoring = False
        self._monitor_tasks = []

    async def fetch_metrics(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(f"{url}/metrics") as response:
            response.raise_for_status()
            return await response.text()

    def parse_histogram(self, content: str, pattern: str) -> dict:
        matches = re.findall(pattern, content, re.MULTILINE)
        histogram = {}

        for line in matches[:-1]:
            match = re.search(self.bucket_pattern, line, re.IGNORECASE)
            if match:
                histogram[float(match.group(1))] = float(match.group(2))

        # last bucket is treated separately because of key '+Inf' instead of number
        match = re.search(self.bucket_pattern, matches[-1], re.IGNORECASE)
        if match:
            histogram[inf] = float(match.group(2))

        return histogram

    def update_histogram(
        self, new_histogram: dict, last_histogram: dict, diff_histogram: dict
    ):
        new_diff_histogram = {}
        if last_histogram:
            for key in last_histogram:
                new_diff_histogram[key] = new_histogram.get(
                    key, 0
                ) - last_histogram.get(key, 0)

        last_histogram.update(new_histogram)
        diff_histogram.update(new_diff_histogram)

    async def update_all_metrics_for_server(
        self, session: aiohttp.ClientSession, url: str
    ) -> None:
        """Fetch metrics once and update histograms for different patterns."""
        content = await self.fetch_metrics(session, url)
        if not content:
            return

        # Process histograms for different patterns
        for pattern, last_histograms, diff_histograms in [
            (
                self.e2e_latency_pattern,
                self.e2e_latency_last_histograms,
                self.e2e_latency_diff_histograms,
            ),
            (
                self.time_to_first_token_pattern,
                self.time_to_first_token_last_histograms,
                self.time_to_first_token_diff_histograms,
            ),
        ]:
            new_histogram = self.parse_histogram(content, pattern)
            self.update_histogram(
                new_histogram,
                last_histograms.setdefault(url, {}),
                diff_histograms.setdefault(url, {}),
            )

    async def _monitor_server(self, url: str, interval: int) -> None:
        async with aiohttp.ClientSession() as session:
            while self.monitoring:
                try:
                    await self.update_all_metrics_for_server(session, url)
                    logging.debug("Metrics updated for %s", url)
                    logging.debug(
                        "e2e latency histogram: %s",
                        self.e2e_latency_diff_histograms[url],
                    )
                    logging.debug(
                        "time-to-first-token histogram: %s",
                        self.time_to_first_token_diff_histograms[url],
                    )
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    logging.debug("Monitoring task cancelled for %s", url)
                    break

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
        tasks = getattr(self, "_monitor_tasks", [])
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.debug("Monitoring stopped for all servers.")

    def choose_server(self) -> VLLMServer:
        scores = {}
        for url in self.urls:
            e2e_histogram = self.e2e_latency_diff_histograms[url]
            e2e_bucket_95 = get_percentile(e2e_histogram)
            tft_histogram = self.time_to_first_token_diff_histograms[url]
            tft_bucket_95 = get_percentile(tft_histogram)
            scores[url] = business_score(e2e_bucket_95, tft_bucket_95)
        url_least_busy = least_busy(scores)
        # Only at choose time, we find back the server object corresponding to the chosen url,
        # because that's what the abstract class declared (more straightforward for the consumer)
        for server in self.servers:
            if server.url == url_least_busy:
                return server
        return None
        # Shouldn't happen since url_least_busy is one of self.urls,
        # which itself is built from self.servers
