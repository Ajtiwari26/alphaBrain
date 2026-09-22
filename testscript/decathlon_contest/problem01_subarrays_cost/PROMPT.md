Write a production-grade, highly optimized Python implementation of Divide an Array Into Subarrays With Minimum Cost II (LeetCode 3013).

Save your implementation into a single standalone file named `minimum_cost.py`.

### Target Function Signature
```python
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
```

### Specifications & Complexity
- Equivalent to finding index 0, plus the minimum sum of (k - 1) elements within any sliding window of size `dist` starting from index 1 to n - 1.
- Must run in $O(N \log N)$ or $O(N \log dist)$ time using dual heaps/multisets with lazy deletion, or a balanced tree.
- Any $O(N \cdot dist)$ approach will strictly TLE on $N = 20,000$.

Output ONLY the complete Python code in `minimum_cost.py` without markdown backticks or commentary so it can be written directly to file.
