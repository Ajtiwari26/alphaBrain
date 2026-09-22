def find_compatible_numbers(nums: list[int]) -> list[int]:
    """
    Given an array of integers nums, for each element nums[i], find any element nums[j] in the array
    such that (nums[i] & nums[j]) == 0 (bitwise AND equals zero).
    If no such element exists in nums, the answer for nums[i] should be -1.
    All integers in nums satisfy 0 <= nums[i] < 2^18 (18 bits).
    Overall time complexity must be O(N + B * 2^B) using Sum Over Subsets (SOS) Dynamic Programming.
    """
    if not nums:
        return []

    max_val = max(nums)
    b = max(18, max_val.bit_length() if max_val > 0 else 1)

    max_mask = 1 << b
    all_mask = max_mask - 1

    dp = [-1] * max_mask
    for x in nums:
        dp[x] = x

    for i in range(b):
        bit = 1 << i
        step = bit << 1
        for base in range(bit, max_mask, step):
            for m in range(base, base + bit):
                if dp[m] == -1:
                    dp[m] = dp[m - bit]

    return [dp[all_mask ^ x] for x in nums]
