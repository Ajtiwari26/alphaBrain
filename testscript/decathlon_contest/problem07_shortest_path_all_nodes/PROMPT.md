Write a production-grade, highly optimized Python implementation of Shortest Path Visiting All Nodes (LeetCode 847).

Save your implementation into a single standalone file named `shortest_path_nodes.py`.

### Target Function Signature
```python
def shortest_path_length(graph: list[list[int]]) -> int:
    """
    You have an undirected, connected graph of n nodes labeled from 0 to n - 1.
    You are given an array graph where graph[i] is a list of all the nodes connected with node i by an edge.
    Return the length of the shortest path that visits every node. You may start and stop at any node,
    you may revisit nodes multiple times, and you may reuse edges.
    """
```

### Specifications & Complexity
- Constraints: 1 <= n <= 12.
- Must use Multi-Source Breadth-First Search (BFS) with bitmask state space (u, mask) in $O(n^2 2^n)$ time.
- Any unpruned recursive DFS or brute force TSP will cause Time Limit Exceeded (TLE) or Memory Limit Exceeded (MLE).

Output ONLY the complete Python code in `shortest_path_nodes.py` without markdown backticks or commentary so it can be written directly to file.
