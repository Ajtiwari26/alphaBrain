Write a production-grade, highly optimized Python implementation of Median of Two Sorted Arrays (LeetCode 4).

Save your implementation into a single standalone file named `median_arrays.py`.

### Target Function Signature
```python
def find_median_sorted_arrays(nums1: list[int], nums2: list[int]) -> float:
    """
    Given two sorted arrays nums1 and nums2 of size m and n respectively,
    return the median of the two sorted arrays.
    The overall run time complexity should be O(log(min(m, n))).
    """
```

### Specifications & Complexity
- Must run in strict $O(\log(\min(m, n)))$ time by binary searching the partition cut on the smaller array.
- Any $O(m + n)$ linear merge or sort approach will fail asymptotic validation.
- Accurately handle empty arrays, singletons, even/odd combined parity, and non-overlapping ranges.

Output ONLY the complete Python code in `median_arrays.py` without markdown backticks or commentary so it can be written directly to file.
