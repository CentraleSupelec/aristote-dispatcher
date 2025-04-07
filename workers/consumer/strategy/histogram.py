from __future__ import annotations

import re
from math import inf


class Histogram(dict[float, float]):
    """Represents a latency histogram mapping latency thresholds to counts."""

    bucket_pattern = r'le="([\d+.inf]+)".*? (\d+\.\d+)'

    def __sub__(self, other: Histogram) -> Histogram:
        """Returns a histogram representing the difference between two histograms."""
        return Histogram(
            {
                key: self.get(key, 0) - other.get(key, 0)
                for key in set(self.keys()) | set(other.keys())
            }
        )

    def diff(self, other: Histogram) -> Histogram:
        """Alias for subtraction for semantic clarity."""
        return self - other

    @staticmethod
    def parse(content: str, pattern: str) -> Histogram:
        matches = re.findall(pattern, content, re.MULTILINE)
        histogram = Histogram()

        # when no request have ever been recorded, vllm does not expose empty histograms
        # so matches can be None
        if matches:
            for line in matches[:-1]:
                match = re.search(Histogram.bucket_pattern, line, re.IGNORECASE)
                if match:
                    histogram[float(match.group(1))] = float(match.group(2))

            # last bucket is treated separately because of key '+Inf' instead of number
            match = re.search(Histogram.bucket_pattern, matches[-1], re.IGNORECASE)
            if match:
                histogram[inf] = float(match.group(2))

        return histogram
