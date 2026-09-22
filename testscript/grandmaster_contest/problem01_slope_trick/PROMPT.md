Write a production-grade, highly optimized Python implementation of Minimum Operations to Make Array Strictly Increasing (Codeforces 713C / Slope Trick).

Save your implementation into a single standalone file named `slope_trick.py`.

### Target Function Signature
```python
def min_operations_increasing(nums: list[int]) -> int:
    """
    Given an array of integers nums, find the minimum number of operations to make the array
    strictly increasing (nums[0] < nums[1] < nums[2] < ... < nums[n-1]).
    In one operation, you can increase or decrease any element by 1 (L1 distance minimization).
    Overall time complexity must be O(N log N) using the Slope Trick / Convex Function Optimization.
    """
```

### Specifications & Complexity
- Standard dynamic programming runs in $O(N^2)$ or $O(N \cdot \text{distinct}(A))$ and will strictly TLE on $N = 50,000$.
- Must reduce the strictly increasing requirement to non-decreasing by transforming elements: $A'_i = A_i - i$.
- Must maintain the convex piecewise-linear objective function using a priority queue / max-heap tracking the slope inflection points in $O(N \log N)$ time and $O(N)$ space.
- Handle empty arrays, singletons, already strictly increasing sequences, reverse sequences, and negative values.

Output ONLY the complete Python code in `slope_trick.py` without markdown backticks or commentary so it can be written directly to file.
