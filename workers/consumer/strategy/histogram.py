from __future__ import annotations


class Histogram(dict[float, float]):
    """Represents a latency histogram mapping latency thresholds to counts."""

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
