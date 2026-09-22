"""
Sliding Window Median (LeetCode 480)
Production-grade, highly optimized O(N log K) implementation using a balanced dual-heap
with hash-map based lazy deletion.
"""

import heapq
from collections import defaultdict


class _DualHeap:
    """
    Balanced dual-heap data structure with lazy deletion support.

    Invariants:
    - small (max-heap) holds the lower half of numbers (represented as -val).
    - large (min-heap) holds the upper half of numbers (represented as val).
    - If k is odd, len(small) == len(large) + 1.
    - If k is even, len(small) == len(large).
    - Stale elements that left the window are tracked in `delayed` and pruned lazily
      from the tops of the heaps.
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
        """Prune invalid (delayed) elements from the top of the small heap."""
        while self.small:
            val = -self.small[0]
            if self.delayed[val] > 0:
                self.delayed[val] -= 1
                heapq.heappop(self.small)
            else:
                break

    def _prune_large(self) -> None:
        """Prune invalid (delayed) elements from the top of the large heap."""
        while self.large:
            val = self.large[0]
            if self.delayed[val] > 0:
                self.delayed[val] -= 1
                heapq.heappop(self.large)
            else:
                break

    def _make_balance(self) -> None:
        """Rebalance the sizes of small and large heaps to maintain the size invariant."""
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
        """Mark an element for deletion, adjust logical size, and rebalance."""
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
        Return the current median with double-precision accuracy.
        Guards against overflow and ensures tops are pruned.
        """
        self._prune_small()
        self._prune_large()
        if self.k & 1:
            return float(-self.small[0])
        # In Python, arbitrary-precision integers avoid 32-bit/64-bit integer overflow.
        # Division by 2.0 yields standard IEEE 754 double precision float.
        return (-self.small[0] + self.large[0]) / 2.0


def median_sliding_window(nums: list[int], k: int) -> list[float]:
    """
    Given an integer array nums and an integer window size k, return the median array
    for each sliding window of size k moving from left to right.

    Parameters:
        nums: list of integers (can include negative values and duplicates).
        k: integer window size (1 <= k <= len(nums)).

    Returns:
        list of floats representing the median of each window.
        - If k is odd, the median is the center value of the sorted window.
        - If k is even, the median is the mean of the two center values.
    """
    if not nums or k <= 0:
        return []

    # Fast path for k = 1: each element is its own median
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
