def super_egg_drop(k: int, n: int) -> int:
    """
    You are given k identical eggs and you have access to a building with n floors labeled from 1 to n.
    You know that there exists a floor f where 0 <= f <= n such that any egg dropped at a floor higher than f
    will break, and any egg dropped at or below floor f will not break.
    Return the minimum number of moves that you need to determine with certainty what the value of f is.
    """
    if k == 1:
        return n
    if n <= 1:
        return n

    dp = [0] * (k + 1)
    moves = 0

    while dp[k] < n:
        moves += 1
        for i in range(k, 0, -1):
            dp[i] += dp[i - 1] + 1

    return moves
