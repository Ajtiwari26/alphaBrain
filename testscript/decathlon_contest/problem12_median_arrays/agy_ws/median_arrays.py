"""
Median of Two Sorted Arrays (LeetCode 4)

Production-grade, highly optimized Python implementation of Median of Two Sorted Arrays
running in strict O(log(min(m, n))) time complexity and O(1) auxiliary space by binary
searching the partition cut on the smaller array.
"""

from __future__ import annotations

import sys


def find_median_sorted_arrays(nums1: list[int], nums2: list[int]) -> float:
    """
    Given two sorted arrays nums1 and nums2 of size m and n respectively,
    return the median of the two sorted arrays.
    The overall run time complexity should be O(log(min(m, n))).

    Algorithm & Mathematical Derivation:
        - Let m = len(nums1) and n = len(nums2).
        - Without loss of generality, assume m <= n (if m > n, swap nums1 and nums2).
        - We wish to partition the union of nums1 and nums2 into two halves:
          Left Half of size (m + n + 1) // 2 and Right Half of size (m + n) // 2.
        - Let partition cut i be in nums1 in range [0, m], and cut j in nums2:
          j = (m + n + 1) // 2 - i.
          Because m <= n, 0 <= i <= m implies 0 <= j <= n.
        - Left elements:
          max_left1 = nums1[i - 1] if i > 0 else -infinity
          max_left2 = nums2[j - 1] if j > 0 else -infinity
        - Right elements:
          min_right1 = nums1[i] if i < m else +infinity
          min_right2 = nums2[j] if j < n else +infinity
        - The partition is valid iff:
          max_left1 <= min_right2 and max_left2 <= min_right1.
        - If max_left1 > min_right2: i is too large, search left (high = i - 1).
        - If max_left2 > min_right1: i is too small, search right (low = i + 1).
        - Once found:
          If (m + n) % 2 == 1:
              median = max(max_left1, max_left2)
          Else:
              median = (max(max_left1, max_left2) + min(min_right1, min_right2)) / 2.0

    Complexity:
        - Time: O(log(min(m, n))) binary search iterations over the smaller array.
        - Space: O(1) auxiliary space.
    """
    m, n = len(nums1), len(nums2)

    if m + n == 0:
        raise ValueError("Cannot compute median of two empty arrays.")

    # Ensure binary search is performed on the smaller array for O(log(min(m, n)))
    if m > n:
        nums1, nums2 = nums2, nums1
        m, n = n, m

    low = 0
    high = m
    half_len = (m + n + 1) // 2

    inf = float("inf")

    while low <= high:
        i = (low + high) // 2
        j = half_len - i

        max_left1 = nums1[i - 1] if i > 0 else -inf
        min_right1 = nums1[i] if i < m else inf

        max_left2 = nums2[j - 1] if j > 0 else -inf
        min_right2 = nums2[j] if j < n else inf

        if max_left1 <= min_right2 and max_left2 <= min_right1:
            # Correct partition found
            if (m + n) % 2 == 1:
                return float(max(max_left1, max_left2))
            return (max(max_left1, max_left2) + min(min_right1, min_right2)) / 2.0
        elif max_left1 > min_right2:
            # i is too large; reduce search boundary
            high = i - 1
        else:
            # max_left2 > min_right1; i is too small; increase search boundary
            low = i + 1

    raise RuntimeError("Input arrays are not sorted.")


class Solution:
    """LeetCode compatible class wrapper for Median of Two Sorted Arrays (LeetCode 4)."""

    def findMedianSortedArrays(self, nums1: list[int], nums2: list[int]) -> float:
        """LeetCode entry point."""
        return find_median_sorted_arrays(nums1, nums2)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        import json

        try:
            arr1 = json.loads(sys.argv[1])
            arr2 = json.loads(sys.argv[2])
            print(find_median_sorted_arrays(arr1, arr2))
        except (json.JSONDecodeError, ValueError) as err:
            print(f"Error parsing CLI input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # Canonical self-tests
        assert find_median_sorted_arrays([1, 3], [2]) == 2.0
        assert find_median_sorted_arrays([1, 2], [3, 4]) == 2.5
        assert find_median_sorted_arrays([], [1]) == 1.0
        assert find_median_sorted_arrays([2], []) == 2.0
        assert find_median_sorted_arrays([0, 0], [0, 0]) == 0.0
        assert find_median_sorted_arrays([1], [2, 3, 4, 5, 6]) == 3.5
        print("Self-tests passed successfully!")
