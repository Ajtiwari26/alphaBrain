Write a production-grade, highly optimized Python implementation of Kalila and Dimna in the Logging Industry (Codeforces 319C / Convex Hull Trick).

Save your implementation into a single standalone file named `kalila_dimna.py`.

### Target Function Signature
```python
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
```

### Specifications & Complexity
- Standard dynamic programming runs in $O(N^2)$ time ($dp[i] = \min_{j < i} (dp[j] + b_j \cdot a_i)$) and will strictly TLE on $N = 50,000$.
- Must use the **Convex Hull Trick** maintaining the lower envelope of lines $y = m x + c$ (where slope $m = b_j$ is decreasing and query $x = a_i$ is increasing).
- Maintain lines in a double-ended queue (deque) with amortized $O(1)$ operations, achieving total $O(N)$ runtime.
- Accurately handle $N \le 2$, large magnitude integers up to $10^{15}$, and duplicate query coordinates.

Output ONLY the complete Python code in `kalila_dimna.py` without markdown backticks or commentary so it can be written directly to file.
