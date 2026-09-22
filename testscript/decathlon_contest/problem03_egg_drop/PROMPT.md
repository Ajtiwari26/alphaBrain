Write a production-grade, highly optimized Python implementation of Super Egg Drop (LeetCode 887).

Save your implementation into a single standalone file named `super_egg_drop.py`.

### Target Function Signature
```python
def super_egg_drop(k: int, n: int) -> int:
    """
    You are given k identical eggs and you have access to a building with n floors labeled from 1 to n.
    You know that there exists a floor f where 0 <= f <= n such that any egg dropped at a floor higher than f
    will break, and any egg dropped at or below floor f will not break.
    Return the minimum number of moves that you need to determine with certainty what the value of f is.
    """
```

### Specifications & Complexity
- Constraints: 1 <= k <= 100, 1 <= n <= 10^4.
- Must run in $O(K \log N)$ or inverted DP $O(K \cdot M)$ where $M$ is moves.
- Naive $O(K \cdot N^2)$ DP will strictly TLE.

Output ONLY the complete Python code in `super_egg_drop.py` without markdown backticks or commentary so it can be written directly to file.
