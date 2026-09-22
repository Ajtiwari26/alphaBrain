"""
Divide an Array Into Subarrays With Minimum Cost II (LeetCode 3013).

Given an integer array nums, and two integers k and dist, divide nums into k contiguous subarrays.
The cost is the sum of the first elements of each subarray.
The first subarray always starts at index 0.
The remaining k - 1 subarrays start at indices i_1 < i_2 < ... < i_{k-1} such that
i_{k-1} - i_1 <= dist.
Return the minimum possible cost.

Equivalence:
Finding nums[0] + min sum of (k - 1) elements in any sliding window of size (dist + 1)
within nums[1:].

Time Complexity: O(N log(dist))
Space Complexity: O(N)
"""

from __future__ import annotations

import heapq


class _DualHeapSlidingWindow:
    """
    Maintains the sum of the m smallest elements in a dynamic sliding window
    using two heaps (max-heap for the m smallest, min-heap for the rest)
    with index-based lazy deletion.
    """

    __slots__ = ("heap_l", "heap_r", "in_l", "l_size", "m", "n", "r_size", "stale", "sum_l")

    def __init__(self, m: int, n: int) -> None:
        self.m = m
        self.n = n
        self.sum_l: int = 0
        self.l_size: int = 0
        self.r_size: int = 0
        # heap_l stores (-val, idx) -> acts as max-heap
        self.heap_l: list[tuple[int, int]] = []
        # heap_r stores (val, idx) -> acts as min-heap
        self.heap_r: list[tuple[int, int]] = []
        # in_l[i] is True if index i is currently logically in heap_l
        self.in_l: list[bool] = [False] * n
        # stale[i] is True if index i has been removed from the active window
        self.stale: list[bool] = [False] * n

    def _prune_l(self) -> None:
        """Discard deleted elements from the top of heap_l."""
        while self.heap_l and self.stale[self.heap_l[0][1]]:
            heapq.heappop(self.heap_l)

    def _prune_r(self) -> None:
        """Discard deleted elements from the top of heap_r."""
        while self.heap_r and self.stale[self.heap_r[0][1]]:
            heapq.heappop(self.heap_r)

    def add(self, val: int, idx: int) -> None:
        """Insert (val, idx) into the sliding window and preserve partition balance."""
        if self.l_size < self.m:
            self.in_l[idx] = True
            heapq.heappush(self.heap_l, (-val, idx))
            self.l_size += 1
            self.sum_l += val
        else:
            self._prune_l()
            if self.heap_l and val < -self.heap_l[0][0]:
                self.in_l[idx] = True
                heapq.heappush(self.heap_l, (-val, idx))
                self.sum_l += val
                # Rebalance: move maximum of heap_l to heap_r
                neg_v, top_idx = heapq.heappop(self.heap_l)
                self.in_l[top_idx] = False
                heapq.heappush(self.heap_r, (-neg_v, top_idx))
                self.sum_l -= -neg_v
                self.r_size += 1
            else:
                self.in_l[idx] = False
                heapq.heappush(self.heap_r, (val, idx))
                self.r_size += 1

    def remove(self, val: int, idx: int) -> None:
        """Mark (val, idx) as removed from the window and rebalance heap_l."""
        self.stale[idx] = True
        if self.in_l[idx]:
            self.l_size -= 1
            self.sum_l -= val
            self._prune_l()
            if self.r_size > 0:
                self._prune_r()
                v, top_idx = heapq.heappop(self.heap_r)
                self.in_l[top_idx] = True
                heapq.heappush(self.heap_l, (-v, top_idx))
                self.l_size += 1
                self.r_size -= 1
                self.sum_l += v
        else:
            self.r_size -= 1
            self._prune_r()


def minimum_cost(nums: list[int], k: int, dist: int) -> int:
    """
    You are given an integer array nums of length n, and two integers k and dist.
    You must divide nums into k contiguous subarrays.
    The cost of dividing nums is the sum of the first elements of each of the k subarrays.
    The first element of the first subarray is always nums[0].
    The distance between the start index of the second subarray and the start index of the
    k-th subarray must be at most dist. That is, if the start indices of the subarrays are
    0 = i_0 < i_1 < i_2 < ... < i_{k-1}, then i_{k-1} - i_1 <= dist.
    Return the minimum possible cost.
    """
    n = len(nums)
    if k == 1:
        return nums[0]

    m = k - 1
    # The valid window of candidate starting indices is at most dist + 1 elements
    window_len = dist + 1
    initial_end = min(n - 1, window_len)

    window = _DualHeapSlidingWindow(m, n)

    # Populate initial window: indices 1 to initial_end
    for i in range(1, initial_end + 1):
        window.add(nums[i], i)

    min_sum = window.sum_l

    # Slide the window through the rest of the array
    for r in range(initial_end + 1, n):
        window.add(nums[r], r)
        out_idx = r - window_len
        window.remove(nums[out_idx], out_idx)
        min_sum = min(min_sum, window.sum_l)

    return nums[0] + min_sum


class Solution:
    """LeetCode submission adapter."""

    def minimumCost(self, nums: list[int], k: int, dist: int) -> int:
        return minimum_cost(nums, k, dist)
