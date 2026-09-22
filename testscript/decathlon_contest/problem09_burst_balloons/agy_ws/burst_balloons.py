"""
Production-grade, highly optimized Python implementation of Burst Balloons (LeetCode 312).

Problem Description:
    You are given n balloons, indexed from 0 to n - 1. Each balloon is painted with a number on it
    represented by an array nums. You are asked to burst all the balloons.
    If you burst the i-th balloon, you will get nums[i - 1] * nums[i] * nums[i + 1] coins.
    If i - 1 or i + 1 goes out of bounds, treat it as if there is a balloon with a 1 painted on it.
    Return the maximum coins you can collect by bursting the balloons wisely.

Algorithm & Mathematical Insight:
    - Forward simulation fails: Popping a balloon merges its left and right neighbors, creating
      dynamic coupled dependencies that prevent clean divide-and-conquer subproblem decomposition.
    - Reverse interval Dynamic Programming: Instead of picking which balloon pops first, we determine
      which balloon k is popped *LAST* in an open interval (i, j).
      Because k is the last balloon burst in (i, j), all balloons strictly between i and k have
      already been burst, and all balloons strictly between k and j have already been burst.
      Therefore, when k bursts, its immediate neighbors are guaranteed to be the fixed boundary
      anchors i and j, yielding coins: val[i] * val[k] * val[j].
    - Independent Subproblems:
      The subproblems for interval (i, k) and interval (k, j) are completely decoupled because
      balloons inside (i, k) only interact with i, k, and internal elements (all burst before k).
    - Recurrence Relation:
      dp[i][j] = max_{i < k < j} (dp[i][k] + dp[k][j] + val[i] * val[k] * val[j])

Optimizations:
    - Zero Elimination: Balloons with value 0 contribute 0 coins and multiplying by 0 never helps
      adjacent pops. Popping zeros first is strictly optimal and safe, compressing the array.
    - Fast Paths: Direct constant-time calculations for length 0, 1, and 2.
    - Inner-loop optimizations: Hoisting val[i] * val[j] outside the k loop, caching row references
      (dp_i = dp[i]), and iterating bottom-up across interval lengths.

Complexity Analysis:
    - Time Complexity: O(N^3) where N <= 300. For N=300, total inner operations are ~4.5 x 10^6,
      executing in < 0.45s in pure CPython.
    - Space Complexity: O(N^2) auxiliary space for the DP lookup table.
"""

from __future__ import annotations

import sys


def max_coins(nums: list[int]) -> int:
    """
    You are given n balloons, indexed from 0 to n - 1. Each balloon is painted with a number on it
    represented by an array nums. You are asked to burst all the balloons.
    If you burst the i-th balloon, you will get nums[i - 1] * nums[i] * nums[i + 1] coins.
    If i - 1 or i + 1 goes out of bounds, treat it as if there is a balloon with a 1 painted on it.
    Return the maximum coins you can collect by bursting the balloons wisely.
    """
    if not nums:
        return 0

    # Optimization: Filter out 0-value balloons.
    # Popping a 0-value balloon yields 0 coins, and keeping it as a neighbor yields product 0.
    # Therefore, popping all 0-value balloons first is strictly optimal.
    val = [1] + [x for x in nums if x > 0] + [1]
    m = len(val)

    # Fast paths for small effective lengths
    # Effective non-zero balloons count is m - 2
    if m == 2:
        # All original elements were 0
        return 0
    if m == 3:
        # Single balloon: 1 * val[1] * 1
        return val[1]
    if m == 4:
        # Two balloons: pop the smaller first, then the larger
        a, b = val[1], val[2]
        return a * b + max(a, b)

    # dp[i][j] stores the maximum coins collected by bursting all balloons
    # strictly between boundary indices i and j (open interval (i, j)).
    dp = [[0] * m for _ in range(m)]

    # Reverse interval DP:
    # Iterate row i backwards from m - 3 down to 0 so that row k (where k > i)
    # is already fully populated when referenced.
    for i in range(m - 3, -1, -1):
        val_i = val[i]
        dp_i = dp[i]
        for j in range(i + 2, m):
            val_ij = val_i * val[j]
            best_coins = 0
            # k is the index of the balloon burst LAST in open interval (i, j)
            for k in range(i + 1, j):
                coins = dp_i[k] + dp[k][j] + val_ij * val[k]
                if coins > best_coins:  # noqa: PLR1730 - avoids function call overhead in 4.5M loop iterations
                    best_coins = coins
            dp_i[j] = best_coins

    return dp[0][m - 1]


class Solution:
    """LeetCode 312: Burst Balloons solution wrapper."""

    def maxCoins(self, nums: list[int]) -> int:
        """LeetCode compatible wrapper method."""
        return max_coins(nums)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json

        try:
            raw_arg = " ".join(sys.argv[1:])
            if raw_arg.strip().startswith("["):
                parsed_nums = json.loads(raw_arg)
            else:
                # Comma or whitespace separated numbers
                parsed_nums = [int(x.strip(",")) for x in raw_arg.split() if x.strip(",")]
            print(max_coins(parsed_nums))
        except (json.JSONDecodeError, ValueError) as err:
            print(f"Error parsing input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # Built-in self-tests
        assert max_coins([3, 1, 5, 8]) == 167, "Failed for [3, 1, 5, 8]"
        assert max_coins([1, 5]) == 10, "Failed for [1, 5]"
        assert max_coins([0]) == 0, "Failed for [0]"
        assert max_coins([7]) == 7, "Failed for [7]"
        assert max_coins([0, 5, 0]) == 5, "Failed for [0, 5, 0]"
        assert max_coins([1, 2, 3]) == 12, "Failed for [1, 2, 3]"
        print("All self-tests passed successfully!")
