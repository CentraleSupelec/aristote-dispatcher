from __future__ import annotations

import random
from typing import Dict, List

from ..exceptions import PercentileComputationError, ServerNotFound
from ..vllm_server import VLLMServer
from .metrics_based_strategy import MetricsBasedStrategy
from .metrics_tracker import MetricsTracker


class LeastBusy(MetricsBasedStrategy):

    # MetricsBasedStrategy requires child classes to implement this
    # That's to make sure a strategy based on metrics has a metrics tracker
    @property
    def tracker(self) -> MetricsTracker:
        return self._tracker

    # This allows to setup the async monitoring task at instanciation time
    @classmethod
    async def create(
        cls,
        servers: List[VLLMServer],
        refresh_rate: int,
        refresh_count_per_window: int,
    ) -> LeastBusy:
        tracker = MetricsTracker(
            [s.url for s in servers], refresh_rate, refresh_count_per_window
        )
        await tracker.monitor()
        return cls(servers, tracker)

    @staticmethod
    def get_percentile(
        histogram: dict, percentile: float = 0.95
    ) -> tuple[int, float] | None:
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
        if not histogram:
            return None

        sorted_buckets = sorted(histogram.items())
        total_requests = sorted_buckets[-1][1]
        percentile_count = percentile * total_requests
        for i, (bucket, count) in enumerate(sorted_buckets):
            if count >= percentile_count:
                return (i, bucket)
        raise PercentileComputationError(percentile, histogram)
        # Should never be reached, since count holds total_requests during last iteration,
        # which will always be bigger than percentile*total_requests for percentile<1

    @staticmethod
    def business_score(
        tft_bucket: tuple[int, float] | None,
    ) -> float:
        """
        both buckets have the shape (bucket_index, bucket_value)
        as returned by the get_percentile function
        """
        # for now we only consider the 95% time to first token bucket as score
        return tft_bucket[1] if tft_bucket else -1

    def get_server_score(self, url: str) -> float:
        tft_histogram = self.tracker.time_to_first_token_diff_histograms[url]
        tft_bucket_95 = LeastBusy.get_percentile(tft_histogram)
        return LeastBusy.business_score(tft_bucket_95)

    @staticmethod
    def least_busy(scores: Dict[str, float]) -> tuple[str, float]:
        """
        scores is a dict of shape {url: score} for each server
        """
        min_value = min(scores.values())
        candidates = [k for k, v in scores.items() if v == min_value]
        return random.choice(candidates), min_value

    def choose_server(self) -> tuple[VLLMServer, float | None]:
        scores = {}
        url_least_busy = None
        current_time_to_first_token = None

        for url in self.tracker.urls:
            scores[url] = self.get_server_score(url)

            # edge case: when a server has never received any request,
            # histograms are not exposed and so business score is -1
            # but then it needs a request for us to start effectively monitoring, so we prioritize it
            if scores[url] == -1:
                url_least_busy = url

        if scores and not url_least_busy:
            url_least_busy, current_time_to_first_token = LeastBusy.least_busy(scores)

        for server in self.servers:
            if server.url == url_least_busy:
                return server, current_time_to_first_token

        raise ServerNotFound()
