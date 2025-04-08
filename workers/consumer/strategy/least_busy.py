from __future__ import annotations

import random
from typing import List

from ..exceptions import NoSuitableVllm
from ..vllm_server import VLLMServer
from .metrics_based_strategy import MetricsBasedStrategy
from .metrics_tracker import MetricsTracker


class LeastBusy(MetricsBasedStrategy):

    def __init__(
        self, servers: List[VLLMServer], threshold: float, tracker: MetricsTracker
    ) -> None:
        super().__init__(servers, tracker)
        self.threshold = threshold

    # MetricsBasedStrategy requires child classes to implement this
    # That's to make sure a strategy based on metrics has a metrics tracker
    @property
    def tracker(self) -> MetricsTracker:
        return self._tracker

    # This allows to setup the async monitoring task at instanciation time
    @classmethod
    async def create(cls, servers: List[VLLMServer], threshold: float) -> LeastBusy:
        tracker = MetricsTracker([s.url for s in servers])
        await tracker.monitor()
        return cls(servers, threshold, tracker)

    @staticmethod
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
        if not histogram:
            return None

        sorted_buckets = sorted(histogram.items())
        total_requests = sorted_buckets[-1][1]
        percentile_count = percentile * total_requests
        for i, (bucket, count) in enumerate(sorted_buckets):
            if count >= percentile_count:
                return (i, bucket)
        raise Exception(f"Couldn't find {100*percentile}th percentile for histogram: {histogram}")
        # Should never be reached, since count holds total_requests during last iteration,
        # which will always be bigger than percentile*total_requests for percentile<1

    @staticmethod
    def business_score(
        tft_bucket: tuple[int, float],
    ) -> float:
        """
        both buckets have the shape (bucket_index, bucket_value)
        as returned by the get_percentile function
        """
        # for now we only consider the 95% time to first token bucket as score
        return tft_bucket[1] if tft_bucket else -1

    @staticmethod
    def least_busy(scores: dict, threshold: float) -> str:
        """
        scores is a dict of shape {url: score} for each server
        """
        candidates = [url for url, score in scores.items() if score < threshold]
        if not candidates:
            return ""
        return random.choice(candidates)

    def choose_server(self) -> VLLMServer:
        scores = {}
        url_least_busy = None
        for url in self.tracker.urls:
            tft_histogram = self.tracker.time_to_first_token_diff_histograms[url]
            tft_bucket_95 = LeastBusy.get_percentile(tft_histogram)
            scores[url] = LeastBusy.business_score(tft_bucket_95)
            if scores[url] == -1:
                url_least_busy = url
        # edge case: when a server has never received any request,
        # histograms are not exposed and so business score is -1
        # but then it needs a request for us to start effectively monitoring, so we prioritize it
        if not url_least_busy:
            url_least_busy = LeastBusy.least_busy(scores, self.threshold)
        for server in self.servers:
            if server.url == url_least_busy:
                return server
        raise NoSuitableVllm()
