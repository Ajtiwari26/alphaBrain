import heapq
from collections import defaultdict


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

    n = len(nums)
    if k == 1:
        return [float(x) for x in nums]

    target_small = (k + 1) // 2
    target_large = k // 2

    # Initialize heaps for the first k elements in O(K log K)
    first_k = sorted(nums[:k])
    small = [-x for x in first_k[:target_small]]  # max-heap (stored negated)
    large = first_k[target_small:]               # min-heap

    heapq.heapify(small)
    heapq.heapify(large)

    small_size = target_small
    large_size = target_large

    delayed = defaultdict(int)

    def prune_small() -> None:
        """Discard lazy-deleted elements from top of max-heap 'small'."""
        while small and delayed[-small[0]] > 0:
            val = -heapq.heappop(small)
            delayed[val] -= 1
            if delayed[val] == 0:
                del delayed[val]

    def prune_large() -> None:
        """Discard lazy-deleted elements from top of min-heap 'large'."""
        while large and delayed[large[0]] > 0:
            val = heapq.heappop(large)
            delayed[val] -= 1
            if delayed[val] == 0:
                del delayed[val]

    def rebalance() -> None:
        """Maintain exact target sizes for active elements in dual heaps."""
        nonlocal small_size, large_size
        while small_size > target_small:
            prune_small()
            val = -heapq.heappop(small)
            heapq.heappush(large, val)
            small_size -= 1
            large_size += 1

        while small_size < target_small:
            prune_large()
            val = heapq.heappop(large)
            heapq.heappush(small, -val)
            large_size -= 1
            small_size += 1

        prune_small()
        prune_large()

    def get_median() -> float:
        """Extract exact double-precision median of current active window."""
        prune_small()
        prune_large()
        if k & 1:
            return float(-small[0])
        return (-small[0] + large[0]) / 2.0

    def add_num(val: int) -> None:
        """Insert new incoming element into appropriate heap."""
        nonlocal small_size, large_size
        prune_large()
        if large and val > large[0]:
            heapq.heappush(large, val)
            large_size += 1
        else:
            heapq.heappush(small, -val)
            small_size += 1
        rebalance()

    def remove_num(val: int) -> None:
        """Mark outgoing element for lazy deletion and adjust balance count."""
        nonlocal small_size, large_size
        prune_small()
        if small and val <= -small[0]:
            small_size -= 1
        else:
            large_size -= 1
        delayed[val] += 1
        rebalance()

    medians = [get_median()]

    for i in range(k, n):
        remove_num(nums[i - k])
        add_num(nums[i])
        medians.append(get_median())

    return medians
