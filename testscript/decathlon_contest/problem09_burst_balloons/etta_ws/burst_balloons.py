def max_coins(nums: list[int]) -> int:
    """
    You are given n balloons, indexed from 0 to n - 1. Each balloon is painted with a number on it
    represented by an array nums. You are asked to burst all the balloons.
    If you burst the i-th balloon, you will get nums[i - 1] * nums[i] * nums[i + 1] coins.
    If i - 1 or i + 1 goes out of bounds, treat it as if there is a balloon with a 1 painted on it.
    Return the maximum coins you can collect by bursting the balloons wisely.
    """
    # Remove zeros as bursting them gives 0 coins and bringing non-zero neighbors together is optimal
    val = [1] + [x for x in nums if x > 0] + [1]
    n = len(val)

    if n == 2:
        return 0

    # dp[i][j] stores the max coins obtained by bursting all balloons strictly between index i and j
    dp = [[0] * n for _ in range(n)]

    for length in range(2, n):
        for left in range(0, n - length):
            right = left + length
            val_left_right = val[left] * val[right]
            max_c = 0
            for k in range(left + 1, right):
                coins = dp[left][k] + dp[k][right] + val_left_right * val[k]
                if coins > max_c:
                    max_c = coins
            dp[left][right] = max_c

    return dp[0][n - 1]


if __name__ == "__main__":
    assert max_coins([3, 1, 5, 8]) == 167
    assert max_coins([1, 5]) == 10
    assert max_coins([0]) == 0
    assert max_coins([7]) == 7
    print("All assertions passed successfully.")
