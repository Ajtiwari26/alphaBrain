"""
Production-grade, highly optimized Python implementation of Kalila and Dimna
in the Logging Industry (Codeforces 319C / Convex Hull Trick).

Problem Description:
    You have n trees (numbered 0 to n - 1).
    Tree i has height a[i] and chainsaw recharge cost b[i].
    Constraints:
      a[0] = 1 < a[1] < a[2] < ... < a[n-1] (strictly increasing heights)
      b[0] > b[1] > b[2] > ... > b[n-1] = 0 (strictly decreasing recharge costs)
    You start at tree 0 with initial cost dp[0] = 0.
    Cutting tree i from tree j (j < i) costs: dp[j] + b[j] * a[i].
    Return the minimum total cost to reach tree n - 1 (dp[n-1]).

Mathematical Formulation & Algorithm (Convex Hull Trick):
    1. Dynamic Programming Recurrence:
       dp[i] = min_{0 <= j < i} (dp[j] + b[j] * a[i])
       Letting m_j = b[j], c_j = dp[j], and x = a[i], this evaluates:
       dp[i] = min_{0 <= j < i} (m_j * x + c_j)

    2. Monotonicity & Lower Envelope:
       - Slopes m_j = b[j] are strictly decreasing: m_0 > m_1 > ... > m_{n-1}
       - Query positions x = a[i] are strictly increasing: x_1 < x_2 < ... < x_{n-1}
       These monotonic properties allow maintaining the lower convex hull of lines
       using a double-ended queue (deque) with amortized O(1) insertions and queries.

    3. Redundancy Criterion (Integer Exact Intersection):
       For three consecutive lines L1 = (m1, c1), L2 = (m2, c2), L3 = (m3, c3)
       with m1 > m2 > m3:
       Intersection x_{12} = (c2 - c1) / (m1 - m2)
       Intersection x_{23} = (c3 - c2) / (m2 - m3)
       L2 is redundant if x_{12} >= x_{23}.
       Using cross-multiplication avoids floating-point precision loss on large integers:
           (c2 - c1) * (m2 - m3) >= (c3 - c2) * (m1 - m2)

    4. Monotonic Deque Query:
       Since query coordinates x are non-decreasing, if L0(x) >= L1(x), L0 will never
       be optimal for any future query x' >= x. Thus L0 can be popped from the front
       in O(1) amortized time.

Complexity:
    - Time Complexity: O(N) amortized across all trees. Each line is pushed once
      and popped at most once from the front and back of the deque.
    - Space Complexity: O(N) auxiliary space to store lines in the lower envelope.
"""

from __future__ import annotations

import sys
from collections import deque
from collections.abc import Sequence
from typing import NamedTuple


class Line(NamedTuple):
    """Represents a 2D line y = m * x + c."""

    m: int  # Slope
    c: int  # Y-intercept

    def eval(self, x: int) -> int:
        """Evaluates y = m * x + c for a given query coordinate x."""
        return self.m * x + self.c


class ConvexHullDeque:
    """
    Maintains the lower envelope of a set of lines y = m * x + c for minimum queries.

    Assumptions:
        - Inserted lines have strictly decreasing (or non-increasing) slopes m.
        - Monotonic queries have non-decreasing query coordinates x.
    Operations:
        - add_line(m, c): Amortized O(1)
        - query_monotonic(x): Amortized O(1)
        - query_arbitrary(x): O(log K) using binary search (without popping)
    """

    __slots__ = ("_dq",)

    def __init__(self) -> None:
        self._dq: deque[Line] = deque()

    def __len__(self) -> int:
        return len(self._dq)

    def is_empty(self) -> bool:
        return len(self._dq) == 0

    def add_line(self, m: int, c: int) -> None:
        """
        Adds a line y = m * x + c to the lower envelope.
        The slope m must be <= all previously added slopes.
        """
        dq = self._dq

        # Handle equal slopes: keep the line with the smaller intercept
        if dq and dq[-1].m == m:
            if dq[-1].c <= c:
                return  # Existing line dominates
            dq.pop()  # New line dominates existing line

        # Remove lines that become redundant on the lower envelope
        while len(dq) >= 2:
            l1 = dq[-2]
            l2 = dq[-1]
            # Redundancy check: X(l1, l2) >= X(l2, new_line)
            # (l2.c - l1.c) / (l1.m - l2.m) >= (c - l2.c) / (l2.m - m)
            if (l2.c - l1.c) * (l2.m - m) >= (c - l2.c) * (l1.m - l2.m):
                dq.pop()
            else:
                break

        dq.append(Line(m, c))

    def query_monotonic(self, x: int) -> int:
        """
        Queries the minimum value at x in amortized O(1) time.
        Requires query coordinates x to be non-decreasing across calls.
        """
        if not self._dq:
            raise ValueError("Cannot query an empty ConvexHullDeque.")

        dq = self._dq
        # Pop lines from the front that are suboptimal for x and all future x' >= x
        while len(dq) >= 2 and dq[0].eval(x) >= dq[1].eval(x):
            dq.popleft()

        return dq[0].eval(x)

    def query_arbitrary(self, x: int) -> int:
        """
        Queries the minimum value at x in O(log K) time using binary search.
        Does not mutate the deque; safe for non-monotonic query coordinates.
        """
        if not self._dq:
            raise ValueError("Cannot query an empty ConvexHullDeque.")

        dq = self._dq
        low = 0
        high = len(dq) - 1

        # Ternary search or binary search over intersection points
        while low < high:
            mid = (low + high) // 2
            if dq[mid].eval(x) >= dq[mid + 1].eval(x):
                low = mid + 1
            else:
                high = mid

        return dq[low].eval(x)


def min_logging_cost(a: list[int], b: list[int]) -> int:
    """
    You have n trees (0 to n - 1).
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
    if n == 2:
        return b[0] * a[1]

    # Initialize CHT lower envelope deque
    cht = ConvexHullDeque()

    # Tree 0 base case: dp[0] = 0, line: y = b[0] * x + dp[0]
    cht.add_line(b[0], 0)

    curr_dp: int = 0

    for i in range(1, n):
        # Query minimum cost to reach tree i: dp[i] = min_{j < i} (b[j] * a[i] + dp[j])
        curr_dp = cht.query_monotonic(a[i])

        # For trees before the final destination, register the new recharge line
        if i < n - 1:
            cht.add_line(b[i], curr_dp)

    return curr_dp


def min_logging_cost_reconstruct(a: Sequence[int], b: Sequence[int]) -> tuple[int, list[int]]:
    """
    Computes the minimum logging cost and reconstructs the sequence of chosen trees
    visited from tree 0 to tree n - 1.

    Returns:
        tuple[int, list[int]]: (minimum_cost, list_of_tree_indices)
    """
    n = len(a)
    if n == 0:
        return 0, []
    if n == 1:
        return 0, [0]
    if n == 2:
        return b[0] * a[1], [0, 1]

    # To reconstruct the path, maintain lines along with their original tree index
    # We use a list with a head pointer so lines are not discarded
    lines: list[tuple[int, int, int]] = []  # (m, c, tree_index)
    parent: list[int] = [-1] * n
    dp: list[int] = [0] * n

    lines.append((b[0], 0, 0))
    head = 0

    for i in range(1, n):
        x = a[i]
        # Advance head pointer to the optimal line for query x
        while head + 1 < len(lines):
            m0, c0, _ = lines[head]
            m1, c1, _ = lines[head + 1]
            if m0 * x + c0 >= m1 * x + c1:
                head += 1
            else:
                break

        best_m, best_c, best_idx = lines[head]
        dp[i] = best_m * x + best_c
        parent[i] = best_idx

        if i < n - 1:
            m_new = b[i]
            c_new = dp[i]

            # Redundancy pruning from the back
            while len(lines) >= 2:
                m1, c1, _ = lines[-2]
                m2, c2, _ = lines[-1]
                if (c2 - c1) * (m2 - m_new) >= (c_new - c2) * (m1 - m2):
                    lines.pop()
                    if head >= len(lines):
                        head = len(lines) - 1
                else:
                    break
            lines.append((m_new, c_new, i))

    # Reconstruct optimal path backwards
    path = []
    curr = n - 1
    while curr != -1:
        path.append(curr)
        curr = parent[curr]
    path.reverse()

    return dp[n - 1], path


class KalilaDimnaSolver:
    """Namespace wrapper for Kalila and Dimna solvers."""

    @staticmethod
    def min_logging_cost(a: list[int], b: list[int]) -> int:
        return min_logging_cost(a, b)

    @staticmethod
    def min_logging_cost_reconstruct(a: Sequence[int], b: Sequence[int]) -> tuple[int, list[int]]:
        return min_logging_cost_reconstruct(a, b)


Solution = KalilaDimnaSolver


def main() -> None:
    """
    High-performance competitive programming CLI runner for Codeforces 319C.
    Reads input from standard input and prints the minimum cost.
    """
    input_data = sys.stdin.read().split()
    if not input_data:
        return

    n = int(input_data[0])
    a = [int(x) for x in input_data[1 : n + 1]]
    b = [int(x) for x in input_data[n + 1 : 2 * n + 1]]

    result = min_logging_cost(a, b)
    sys.stdout.write(f"{result}\n")


if __name__ == "__main__":
    main()
