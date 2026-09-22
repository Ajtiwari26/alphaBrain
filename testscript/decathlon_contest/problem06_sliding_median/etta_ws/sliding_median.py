import heapq


def median_sliding_window(nums: list[int], k: int) -> list[float]:
    """
    Return double-precision floating point medians for each sliding window of size k.

    Runs in strict O(N log K) time and O(K) space complexity using dual balanced
    heaps with lazy deletion.

    :param nums: List of integers.
    :param k: Sliding window size (1 <= k <= len(nums)).
    :return: List of window medians as double-precision floats.
    """
    n = len(nums)
    if not nums or k <= 0 or k > n:
        return []

    if k == 1:
        return [float(x) for x in nums]

    # Max-heap for lower half (elements stored as negated ints)
    small: list[int] = []
    # Min-heap for upper half (elements stored as positive ints)
    large: list[int] = []
    # Hash map for lazy deletion: element -> count of pending removals
    delayed: dict[int, int] = {}

    small_size = 0
    large_size = 0

    def prune(heap: list[int], is_max_heap: bool) -> None:
        """Purge invalid (stale/deleted) elements from the top of the heap."""
        while heap:
            num = -heap[0] if is_max_heap else heap[0]
            count = delayed.get(num, 0)
            if count > 0:
                if count == 1:
                    del delayed[num]
                else:
                    delayed[num] = count - 1
                heapq.heappop(heap)
            else:
                break

    def rebalance() -> None:
        """Maintain invariant: small_size == large_size or small_size == large_size + 1."""
        nonlocal small_size, large_size
        if small_size > large_size + 1:
            prune(small, True)
            val = -heapq.heappop(small)
            heapq.heappush(large, val)
            small_size -= 1
            large_size += 1
            prune(small, True)
        elif small_size < large_size:
            prune(large, False)
            val = heapq.heappop(large)
            heapq.heappush(small, -val)
            large_size -= 1
            small_size += 1
            prune(large, False)

    def add_num(num: int) -> None:
        nonlocal small_size, large_size
        prune(small, True)
        if not small or num <= -small[0]:
            heapq.heappush(small, -num)
            small_size += 1
        else:
            heapq.heappush(large, num)
            large_size += 1
        rebalance()

    def remove_num(num: int) -> None:
        nonlocal small_size, large_size
        prune(small, True)
        max_small = -small[0]

        delayed[num] = delayed.get(num, 0) + 1

        if num <= max_small:
            small_size -= 1
            if num == max_small:
                prune(small, True)
        else:
            large_size -= 1
            if large and num == large[0]:
                prune(large, False)

        rebalance()

    def get_median() -> float:
        prune(small, True)
        if k & 1:
            return float(-small[0])
        else:
            prune(large, False)
            return (-small[0] + large[0]) / 2.0

    # Build initial window
    for i in range(k):
        add_num(nums[i])

    result_len = n - k + 1
    result: list[float] = [0.0] * result_len
    result[0] = get_median()

    # Slide window
    for i in range(k, n):
        add_num(nums[i])
        remove_num(nums[i - k])
        result[i - k + 1] = get_median()

    return result


if __name__ == "__main__":
    # Quick sanity check
    test_nums = [1, 3, -1, -3, 5, 3, 6, 7]
    test_k = 3
    expected = [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
    output = median_sliding_window(test_nums, test_k)
    assert output == expected, f"Expected {expected}, got {output}"
    print("All checks passed successfully.")
