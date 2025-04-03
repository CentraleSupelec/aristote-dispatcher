import asyncio
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

        asyncio.run(self.monitor())

    async def update_histogram(
        self, session: aiohttp.ClientSession, url: str, pattern: str
    ) -> None:
        try:
            async with session.get(url) as response:
                content = await response.text()

            # all 'bucket' lines
            res = re.findall(pattern, content, re.MULTILINE)
            new_histogram = {}

            for line in res[:-1]:
                match = re.search(self.bucket_pattern, line, re.IGNORECASE)
                if match:
                    new_histogram[float(match.group(1))] = float(match.group(2))

            # last bucket is treated separately because of key '+Inf' instead of number
            match = re.search(self.bucket_pattern, res[-1], re.IGNORECASE)
            if match:
                new_histogram[inf] = float(match.group(2))

            if pattern == self.e2e_latency_pattern:
                last_histogram = self.e2e_latency_last_histograms[url]
                diff_histogram = self.e2e_latency_diff_histograms[url]
            else:
                last_histogram = self.time_to_first_token_last_histograms[url]
                diff_histogram = self.time_to_first_token_diff_histograms[url]

            new_diff_histogram = {}
            if last_histogram:
                for key in last_histogram:
                    new_diff_histogram[key] = new_histogram.get(
                        key, 0
                    ) - last_histogram.get(key, 0)

            last_histogram.update(new_histogram)
            diff_histogram.update(new_diff_histogram)

        except Exception as e:
            print(f"Error updating metrics from {url}: {str(e)}")

    async def update_all_metrics_for_server(
        self, session: aiohttp.ClientSession, url: str
    ) -> None:
        await asyncio.gather(
            self.update_histogram(session, url, self.e2e_latency_pattern),
            self.update_histogram(session, url, self.time_to_first_token_pattern),
        )

    async def _monitor_server(self, url: str, interval: int) -> None:
        async with aiohttp.ClientSession() as session:
            while self.monitoring:
                await self.update_all_metrics_for_server(session, url)
                print(f"Metrics updated for {url}")
                print(f"e2e latency histogram: {self.e2e_latency_diff_histograms[url]}")
                print(
                    f"time-to-first-token histogram: {self.time_to_first_token_diff_histograms[url]}"
                )
                await asyncio.sleep(interval)

    async def monitor(self, interval: int = 10) -> None:
        if self.monitoring:
            print("Monitoring is already running.")
            return

        self.monitoring = True
        tasks = [self._monitor_server(url, interval) for url in self.urls]
        print(f"Started monitoring for {len(self.urls)} servers")
        await asyncio.gather(*tasks)

    def stop_monitor(self) -> None:
        if not self.monitoring:
            print("Monitoring is not running.")
            return

        self.monitoring = False
        print("Monitoring stopped for all servers.")

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
