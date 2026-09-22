Write a production-grade, highly optimized Python implementation of the Sliding Window Median algorithm (LeetCode 480).

Save your implementation into a single standalone file named `sliding_median.py`.

### Target Function Signature
```python
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
```

### Specifications & Requirements
1. **Asymptotic Complexity Requirement**:
   - Must achieve $O(N \log K)$ overall time complexity.
   - Naive re-sorting in $O(N \cdot K \log K)$ or $O(N \cdot K)$ will fail scalability stress tests on large inputs ($N = 30,000, K = 15,000$).
   - Implement a balanced dual-heap (`max_heap` for lower half, `min_heap` for upper half) with a hash-map-based **lazy deletion** mechanism for out-of-window elements, or an efficient balanced tree/fenwick approach.
2. **Precision & Integer Overflow**:
   - Return floating point values with full double-precision floating point accuracy.
   - Guard against integer overflow when averaging extreme 32-bit integers.
3. **Edge Cases**:
   - Handle $k = 1$ and $k = \text{len}(nums)$ without special-case performance degradation.
   - Correctly handle duplicate values and negative integers.

Output ONLY the complete Python code in `sliding_median.py` without markdown backticks or commentary so it can be written directly to file.
