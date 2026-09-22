Write a production-grade, highly optimized Python implementation of Burst Balloons (LeetCode 312).

Save your implementation into a single standalone file named `burst_balloons.py`.

### Target Function Signature
```python
def max_coins(nums: list[int]) -> int:
    """
    You are given n balloons, indexed from 0 to n - 1. Each balloon is painted with a number on it
    represented by an array nums. You are asked to burst all the balloons.
    If you burst the i-th balloon, you will get nums[i - 1] * nums[i] * nums[i + 1] coins.
    If i - 1 or i + 1 goes out of bounds, treat it as if there is a balloon with a 1 painted on it.
    Return the maximum coins you can collect by bursting the balloons wisely.
    """
```

### Specifications & Complexity
- Constraints: 1 <= nums.length <= 300, 0 <= nums[i] <= 100.
- Must run in $O(N^3)$ time using reverse interval Dynamic Programming (evaluating which balloon is popped *last* in interval `[i, j]`).
- Forward simulation or brute-force backtracking will cause TLE.

Output ONLY the complete Python code in `burst_balloons.py` without markdown backticks or commentary so it can be written directly to file.
