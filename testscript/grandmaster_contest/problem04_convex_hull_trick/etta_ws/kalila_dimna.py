from collections import deque
import sys


def min_logging_cost(a: list[int], b: list[int]) -> int:
    """You have n trees (0 to n - 1).

    Tree i has height a[i] and recharge cost b[i].
    Constraints:
      a[0] = 1 < a[1] < a[2] < ... < a[n-1] (strictly increasing heights)
      b[0] > b[1] > b[2] > ... > b[n-1] = 0 (strictly decreasing costs)
    You start at tree 0 with initial cost dp[0] = 0.
    Jumping from tree j to tree i (j < i) costs: dp[j] + b[j] * a[i].
    Return the minimum cost to reach tree n - 1 (dp[n-1]).
    Overall time complexity must be O(N) using the Convex Hull Trick (CHT) or O(N log N) via Li Chao Tree.
    """
    n = len(a)
    if n <= 1:
        return 0

    dq = deque()
    dq.append((b[0], 0))

    dp_i = 0
    for i in range(1, n):
        x = a[i]

        while len(dq) >= 2:
            m0, c0 = dq[0]
            m1, c1 = dq[1]
            if m0 * x + c0 >= m1 * x + c1:
                dq.popleft()
            else:
                break

        m_best, c_best = dq[0]
        dp_i = m_best * x + c_best

        m3, c3 = b[i], dp_i

        while len(dq) >= 2:
            m1, c1 = dq[-2]
            m2, c2 = dq[-1]
            if (c3 - c2) * (m1 - m2) <= (c2 - c1) * (m2 - m3):
                dq.pop()
            else:
                break

        dq.append((m3, c3))

    return dp_i


if __name__ == "__main__":
    input_data = sys.stdin.read().split()
    if input_data:
        n = int(input_data[0])
        a = [int(x) for x in input_data[1 : n + 1]]
        b = [int(x) for x in input_data[n + 1 : 2 * n + 1]]
        print(min_logging_cost(a, b))
