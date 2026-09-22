"""
Production-grade, highly optimized implementation of Super Egg Drop (LeetCode 887).

Problem:
    Given k identical eggs and a building with n floors labeled from 1 to n,
    determine the minimum number of moves needed to find the critical floor f
    (0 <= f <= n) where eggs break above f and survive at or below f.

Complexity Analysis:
    - Standard DP: O(K * N^2) - strictly TLE.
    - Binary Search DP: O(K * N log N) - slow for N = 10^4.
    - Inverted DP: O(K * M) time, O(K) space, where M is the minimum moves needed.
      Because M <= 141 when K >= 2 and N <= 10^4, and K is effectively capped at
      ceil(log2(N + 1)) <= 14, total operations are <= 300.
    - Combinatorial Binary Search: O(K log N) time, O(1) space.
"""

from __future__ import annotations

import sys


def super_egg_drop(k: int, n: int) -> int:
    """
    You are given k identical eggs and you have access to a building with n floors labeled from 1 to n.
    You know that there exists a floor f where 0 <= f <= n such that any egg dropped at a floor higher than f
    will break, and any egg dropped at or below floor f will not break.
    Return the minimum number of moves that you need to determine with certainty what the value of f is.
    """
    if k <= 0 or n <= 0:
        return 0
    if k == 1 or n <= 1:
        return n

    # With M moves, the maximum number of eggs that could ever break during an optimal
    # binary search strategy is bounded by ceil(log2(n + 1)) = n.bit_length().
    # Having more eggs than this threshold cannot reduce the required moves.
    k = min(k, n.bit_length())

    # dp[i] denotes the maximum number of floors that can be conclusively tested
    # with the current number of moves and i eggs.
    # Recurrence: dp[i] = dp[i] (egg survives) + dp[i-1] (egg breaks) + 1 (current floor)
    dp: list[int] = [0] * (k + 1)
    moves: int = 0

    while dp[k] < n:
        moves += 1
        for i in range(k, 0, -1):
            dp[i] += dp[i - 1] + 1

    return moves


def super_egg_drop_combinatorics(k: int, n: int) -> int:
    """
    Alternative O(K log N) solver using mathematical combinations and binary search.
    The number of floors tested with m moves and k eggs equals sum_{i=1}^{min(k, m)} C(m, i).
    """
    if k <= 0 or n <= 0:
        return 0
    if k == 1 or n <= 1:
        return n

    k = min(k, n.bit_length())

    def can_cover(m: int) -> bool:
        total = 0
        term = 1
        limit = min(k, m)
        for i in range(1, limit + 1):
            term = term * (m - i + 1) // i
            total += term
            if total >= n:
                return True
        return total >= n

    low, high = 1, n
    ans = n
    while low <= high:
        mid = (low + high) // 2
        if can_cover(mid):
            ans = mid
            high = mid - 1
        else:
            low = mid + 1

    return ans


class Solution:
    """LeetCode compatible class wrapper for Super Egg Drop."""

    def superEggDrop(self, k: int, n: int) -> int:
        return super_egg_drop(k, n)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        try:
            eggs = int(sys.argv[1])
            floors = int(sys.argv[2])
            print(super_egg_drop(eggs, floors))
        except ValueError:
            print("Error: k and n must be integers.", file=sys.stderr)
            sys.exit(1)
    else:
        test_cases = [
            (1, 2, 2),
            (2, 6, 3),
            (3, 14, 4),
            (2, 100, 14),
            (4, 10000, 23),
            (100, 10000, 14),
        ]
        for eggs, floors, expected in test_cases:
            res = super_egg_drop(eggs, floors)
            assert res == expected, f"Failed for k={eggs}, n={floors}: got {res}, expected {expected}"
        print("All default test cases passed successfully.")
