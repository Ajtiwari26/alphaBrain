"""
Production-grade, highly optimized Python implementation of Compatible Numbers
(Codeforces 165E / Sum Over Subsets Dynamic Programming).

Problem Description:
    Given an array of integers nums, for each element nums[i], find any element nums[j]
    in the array such that (nums[i] & nums[j]) == 0 (bitwise AND equals zero).
    If no such element exists in nums, the answer for nums[i] should be -1.
    All integers in nums satisfy 0 <= nums[i] < 2^18 (18 bits).

Mathematical Formulation & Algorithm (Sum Over Subsets / SOS DP):
    1. Bitwise Disjointness Condition:
       Two integers x and y satisfy (x & y) == 0 if and only if they share no set bits.
       In a universe of B bits (masks from 0 to 2^B - 1), let ~x denote the bitwise
       complement of x restricted to B bits:
           ~x = ((1 << B) - 1) ^ x.
       Then (x & y) == 0 is mathematically equivalent to:
           y is a submask of ~x (denoted y ⊆ ~x).

    2. State Space & DP Definition:
       Let dp[mask] denote an element from nums that is a submask of mask (dp[mask] ⊆ mask),
       or -1 if no element in nums is a submask of mask.
       
       Initialization:
           dp[mask] = -1 for all 0 <= mask < 2^B.
           For each x in nums:
               dp[x] = x  (since x ⊆ x).

    3. SOS Multidimensional Transitions:
       A submask y of mask may differ in any of the set bits of mask.
       Instead of iterating over all 3^B submask pairs (which TLEs for B = 18 since 3^18 ≈ 3.87 * 10^8),
       SOS DP transitions along each bit dimension i from 0 to B - 1:
           For each dimension i in [0, B - 1]:
               For each mask with bit i set (mask & (1 << i) != 0):
                   sub = mask ^ (1 << i)
                   if dp[mask] == -1:
                       dp[mask] = dp[sub]
       This guarantees that dp[mask] aggregates reachable values across all 2^popcount(mask)
       subsets in O(B * 2^B) operations.

    4. Answer Retrieval:
       For each nums[i], the bitwise complement within B bits is comp = ((1 << B) - 1) ^ nums[i].
       The compatible number is simply dp[comp].

Complexity:
    - Time Complexity:
        * Table Initialization: O(2^B + N)
        * SOS DP Propagation: O(B * 2^B). For B = 18, B * 2^B = 18 * 262,144 ≈ 4.7 * 10^6 steps.
        * Query Answering: O(N)
        * Overall Time Complexity: O(N + B * 2^B). For N = 100,000, B = 18, executes in < 0.06 seconds.
    - Space Complexity:
        * O(2^B) auxiliary space for the DP array (approx. 2 MB for 2^18 64-bit integers).
"""

from __future__ import annotations

import sys


def find_compatible_numbers(nums: list[int], bit_width: int = 18) -> list[int]:
    """
    Given an array of integers nums, for each element nums[i], find any element nums[j] in the array
    such that (nums[i] & nums[j]) == 0 (bitwise AND equals zero).
    If no such element exists in nums, the answer for nums[i] should be -1.
    All integers in nums satisfy 0 <= nums[i] < 2^18 (18 bits).
    Overall time complexity must be O(N + B * 2^B) using Sum Over Subsets (SOS) Dynamic Programming.
    """
    if not nums:
        return []

    # Validate non-negativity and adapt bit_width if inputs exceed 2^18
    max_val = 0
    for x in nums:
        if x < 0:
            raise ValueError(f"All integers in nums must be non-negative, got {x}")
        max_val = max(max_val, x)

    # Ensure bit_width is sufficient to represent all numbers in nums
    needed_bits = max_val.bit_length()
    bit_width = max(bit_width, needed_bits)

    size = 1 << bit_width
    dp = [-1] * size

    # Base cases: each number in nums is trivially a submask of itself
    for x in nums:
        dp[x] = x

    # SOS DP transitions across each bit dimension 0 <= i < bit_width
    # Iterating over blocks of size (1 << (i + 1)) directly visits only masks with bit i set,
    # eliminating branch mispredictions and redundant checks.
    for i in range(bit_width):
        bit = 1 << i
        step = bit << 1
        for base in range(0, size, step):
            base_bit = base + bit
            for offset in range(bit):
                mask = base_bit + offset
                if dp[mask] == -1:
                    dp[mask] = dp[base + offset]

    # Query phase: complement of x restricted to bit_width bits is all_ones ^ x
    all_ones = size - 1
    return [dp[all_ones ^ x] for x in nums]


class CompatibleNumbersSolver:
    """Convenience class wrapper for Compatible Numbers solvers and LeetCode / competitive interfaces."""

    @staticmethod
    def find_compatible_numbers(nums: list[int], bit_width: int = 18) -> list[int]:
        return find_compatible_numbers(nums, bit_width=bit_width)


Solution = CompatibleNumbersSolver


def main() -> None:
    """CLI and verification demonstration runner."""
    # Check if input is piped via stdin (e.g. Codeforces format: n followed by a_1, ..., a_n)
    if not sys.stdin.isatty():
        input_data = sys.stdin.read().split()
        if input_data:
            n = int(input_data[0])
            nums = [int(v) for v in input_data[1 : n + 1]]
            results = find_compatible_numbers(nums)
            print(" ".join(str(r) for r in results))
            return

    # Default self-test and demonstration cases
    print("=" * 70)
    print("Compatible Numbers (Codeforces 165E / SOS Dynamic Programming)")
    print("=" * 70)

    samples = [
        [],
        [0],
        [1],
        [2, 3, 4],
        [2, 3, 6, 7],
        [5, 10, 5, 10],
        [1, 2, 4, 8, 16],
    ]

    for nums in samples:
        res = find_compatible_numbers(nums)
        print(f"Input : {nums}")
        print(f"Output: {res}")
        # Verify correctness
        for x, ans in zip(nums, res):
            if ans != -1:
                assert (x & ans) == 0, f"Violation: {x} & {ans} != 0"
        print("-" * 70)


if __name__ == "__main__":
    main()
