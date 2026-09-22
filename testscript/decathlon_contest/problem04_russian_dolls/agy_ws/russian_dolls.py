"""
Production-grade, highly optimized Python implementation of Russian Doll Envelopes (LeetCode 354).

Problem Description:
    You are given a 2D array of integers envelopes where envelopes[i] = [w_i, h_i]
    represents the width and height of an envelope. One envelope can fit into another
    if and only if both the width and height of one envelope are strictly greater
    than the other envelope.
    Return the maximum number of envelopes you can Russian doll (i.e., put one inside the other).
    Note: You cannot rotate an envelope.

Algorithm & Complexity:
    - Sort: Sort envelopes by width ascending. For envelopes with the same width,
      sort by height descending. Key: (w, -h).
      Why descending height for equal widths?
      Because envelopes with the same width cannot fit inside one another. Sorting
      height descending guarantees that at most one envelope of any given width can
      be selected in a strictly increasing subsequence of heights.
    - LIS: Find the Longest Increasing Subsequence (LIS) on the sorted heights using
      Patience Sorting / Binary Search (bisect_left).
    - Time Complexity: O(N log N) dominated by sorting and binary searches.
    - Space Complexity: O(N) auxiliary space to store the tail array.
"""

from __future__ import annotations

import bisect
import sys


def max_envelopes(envelopes: list[list[int]]) -> int:
    """
    You are given a 2D array of integers envelopes where envelopes[i] = [w_i, h_i] represents the width and height of an envelope.
    One envelope can fit into another if and only if both the width and height of one envelope are strictly greater than the other envelope.
    Return the maximum number of envelopes you can Russian doll (i.e., put one inside the other).
    Note: You cannot rotate an envelope.
    """
    if not envelopes:
        return 0
    if len(envelopes) == 1:
        return 1

    # Sort envelopes: width ascending, height descending for ties
    envelopes.sort(key=lambda x: (x[0], -x[1]))

    # Patience Sorting (LIS) over heights
    tails: list[int] = []
    for _, h in envelopes:
        # Fast path: if h is strictly greater than the current maximum tail,
        # we can extend the LIS immediately without binary search.
        if not tails or h > tails[-1]:
            tails.append(h)
        else:
            idx = bisect.bisect_left(tails, h)
            tails[idx] = h

    return len(tails)


class Solution:
    """LeetCode compatible class wrapper for Russian Doll Envelopes."""

    def maxEnvelopes(self, envelopes: list[list[int]]) -> int:
        return max_envelopes(envelopes)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json

        try:
            raw_input = " ".join(sys.argv[1:])
            data = json.loads(raw_input)
            print(max_envelopes(data))
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            print(f"Error parsing input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        test_cases = [
            ([[5, 4], [6, 4], [6, 7], [2, 3]], 3),
            ([[1, 1], [1, 1], [1, 1]], 1),
            ([[4, 5], [4, 6], [6, 7], [2, 3], [1, 1]], 4),
            ([[1, 2], [2, 3], [3, 4], [3, 5], [4, 5], [5, 5], [5, 6], [6, 7], [7, 8]], 7),
        ]
        for envs, expected in test_cases:
            res = max_envelopes(envs)
            assert res == expected, f"Failed for {envs}: got {res}, expected {expected}"
        print("All default test cases passed successfully.")
