"""
Sliding Window Median (LeetCode 480)

Production-grade, highly optimized Python implementation of Sliding Window Median
running in strict O(N log K) time using balanced dual-heaps with hash-map based lazy deletion.
"""

from __future__ import annotations

import heapq
import sys
from collections import defaultdict


class _DualHeap:
    """
    Balanced dual-heap data structure with lazy deletion support.

    Invariants:
    - small (max-heap) stores -val for the smaller half.
    - large (min-heap) stores val for the larger half.
    - If k is odd, len(small) == len(large) + 1.
    - If k is even, len(small) == len(large).
    - Invalid elements that left the active window are tracked in `delayed`
      and lazily purged when they surface at the top of either heap.
    """

    __slots__ = ("delayed", "k", "large", "large_size", "small", "small_size")

    def __init__(self, k: int) -> None:
        self.k = k
        self.small: list[int] = []  # max-heap: stores -val
        self.large: list[int] = []  # min-heap: stores val
        self.delayed: defaultdict[int, int] = defaultdict(int)
        self.small_size: int = 0
        self.large_size: int = 0

    def _prune_small(self) -> None:
        """Prune stale elements from the top of the small (max) heap."""
        while self.small:
            val = -self.small[0]
            if self.delayed[val] > 0:
                self.delayed[val] -= 1
                heapq.heappop(self.small)
            else:
                break

    def _prune_large(self) -> None:
        """Prune stale elements from the top of the large (min) heap."""
        while self.large:
            val = self.large[0]
            if self.delayed[val] > 0:
                self.delayed[val] -= 1
                heapq.heappop(self.large)
            else:
                break

    def _make_balance(self) -> None:
        """Rebalance the logical sizes of the two heaps."""
        if self.small_size > self.large_size + 1:
            val = -heapq.heappop(self.small)
            heapq.heappush(self.large, val)
            self.small_size -= 1
            self.large_size += 1
            self._prune_small()
        elif self.small_size < self.large_size:
            val = heapq.heappop(self.large)
            heapq.heappush(self.small, -val)
            self.small_size += 1
            self.large_size -= 1
            self._prune_large()

    def insert(self, num: int) -> None:
        """Insert an element into the appropriate heap and rebalance."""
        if not self.small or num <= -self.small[0]:
            heapq.heappush(self.small, -num)
            self.small_size += 1
        else:
            heapq.heappush(self.large, num)
            self.large_size += 1
        self._make_balance()

    def erase(self, num: int) -> None:
        """Mark an outgoing window element for lazy deletion and rebalance."""
        self.delayed[num] += 1
        if num <= -self.small[0]:
            self.small_size -= 1
            if num == -self.small[0]:
                self._prune_small()
        else:
            self.large_size -= 1
            if self.large and num == self.large[0]:
                self._prune_large()
        self._make_balance()

    def get_median(self) -> float:
        """
        Return the current median with double-precision floating-point accuracy.
        Ensures heap tops are pruned before reading.
        """
        self._prune_small()
        self._prune_large()
        if self.k & 1:
            return float(-self.small[0])
        # Python handles arbitrary precision integers; division yields 64-bit float
        return (-self.small[0] + self.large[0]) / 2.0


def median_sliding_window(nums: list[int], k: int) -> list[float]:
    """
    Return double-precision floating point medians for each sliding window of size k.
    Must run in strict O(N log K) time using balanced dual-heaps with lazy deletion.
    """
    if not nums or k <= 0 or k > len(nums):
        return []

    # Fast path for k = 1: each element is trivially its own median
    if k == 1:
        return [float(x) for x in nums]

    dh = _DualHeap(k)
    for i in range(k):
        dh.insert(nums[i])

    result: list[float] = [dh.get_median()]
    for i in range(k, len(nums)):
        dh.insert(nums[i])
        dh.erase(nums[i - k])
        result.append(dh.get_median())

    return result


class Solution:
    """LeetCode compatible class wrapper for Sliding Window Median (LeetCode 480)."""

    def medianSlidingWindow(self, nums: list[int], k: int) -> list[float]:
        return median_sliding_window(nums, k)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        import json

        try:
            nums_in = json.loads(sys.argv[1])
            k_in = int(sys.argv[2])
            print(median_sliding_window(nums_in, k_in))
        except (json.JSONDecodeError, ValueError) as err:
            print(f"Error parsing CLI input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        sample_nums = [1, 3, -1, -3, 5, 3, 6, 7]
        sample_k = 3
        expected = [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
        actual = median_sliding_window(sample_nums, sample_k)
        assert actual == expected, f"Expected {expected}, got {actual}"
        print("Self-test passed successfully!")
