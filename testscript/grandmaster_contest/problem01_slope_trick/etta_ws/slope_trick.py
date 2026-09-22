import heapq


def min_operations_increasing(nums: list[int]) -> int:
    """
    Given an array of integers nums, find the minimum number of operations to make the array
    strictly increasing (nums[0] < nums[1] < nums[2] < ... < nums[n-1]).
    In one operation, you can increase or decrease any element by 1 (L1 distance minimization).
    Overall time complexity must be O(N log N) using the Slope Trick / Convex Function Optimization.
    """
    if not nums:
        return 0

    max_heap: list[int] = []
    total_operations: int = 0

    for i, num in enumerate(nums):
        # Reduce strictly increasing condition (nums[i] < nums[i+1])
        # to non-decreasing condition (nums[i] - i <= nums[i+1] - (i+1))
        val = num - i

        # Maintain inflection points of the convex function using a max-heap.
        # Store negated values because Python heapq module implements a min-heap.
        heapq.heappush(max_heap, -val)

        # Peak of max-heap represents the rightmost inflection point (optimal end value for current prefix).
        max_val = -max_heap[0]

        # If transformed current value is less than max_val, the non-decreasing order is violated.
        # Update slope inflection points and accumulate the required minimum L1 operations.
        if val < max_val:
            total_operations += max_val - val
            heapq.heappop(max_heap)
            heapq.heappush(max_heap, -val)

    return total_operations


if __name__ == "__main__":
    # Verification & Test Cases
    assert min_operations_increasing([]) == 0
    assert min_operations_increasing([42]) == 0
    assert min_operations_increasing([1, 2, 3, 4, 5]) == 0
    assert min_operations_increasing([5, 4, 3, 2, 1]) == 12
    assert min_operations_increasing([-5, -10, -15]) == 12
    assert min_operations_increasing([1, 5, 2, 3, 4]) == 3
    assert min_operations_increasing([1, 1, 1, 1]) == 4
    print("All slope trick unit tests passed!")
