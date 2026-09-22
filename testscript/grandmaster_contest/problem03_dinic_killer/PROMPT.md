Write a production-grade, highly optimized Python implementation of Maximum Flow using Dinic's Algorithm with Current-Arc Optimization.

Save your implementation into a single standalone file named `max_flow.py`.

### Target Function Signature
```python
def max_flow(n: int, edges: list[tuple[int, int, int]], source: int, sink: int) -> int:
    """
    Computes the maximum network flow from source to sink in a directed graph.
    :param n: Number of vertices (0 to n - 1).
    :param edges: List of tuples (u, v, capacity) representing directed edges with integer capacities.
    :param source: Index of source node.
    :param sink: Index of sink node.
    :return: Maximum flow value as an integer.
    """
```

### Specifications & Complexity
- Must use **Dinic's Algorithm** with:
  1. Breadth-First Search (BFS) to construct level graphs.
  2. Depth-First Search (DFS) with **Current-Arc Pointers** (`work`/`ptr`/`head` array) so dead-ends and saturated edges are not repeatedly rescanned from 0.
- Naive Ford-Fulkerson, Edmonds-Karp, or naive Dinic without current-arc optimization will strictly TLE on adversarial layered killer graphs with $V = 2,000$ and $E = 12,000$.
- Handle multi-edges, reverse residual edges, disconnected components, and unit networks.

Output ONLY the complete Python code in `max_flow.py` without markdown backticks or commentary so it can be written directly to file.
