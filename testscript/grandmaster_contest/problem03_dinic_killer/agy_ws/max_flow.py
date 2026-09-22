"""
Production-grade, highly optimized Python implementation of Maximum Flow
using Dinic's Algorithm with Current-Arc Optimization.

Specifications & Complexity:
    - Algorithm: Dinic's Algorithm (Level Graph BFS + Blocking Flow DFS)
    - Optimizations:
        1. Current-Arc Pointers (`ptr` / `work` array) preventing repeated edge rescanning.
        2. Dead-end pruning (`level[u] = -1`) to eliminate unproductive DFS re-entries.
        3. Compact residual edge storage via paired indices (`e ^ 1` for residual edge).
        4. Zero-allocation circular queue for BFS level assignment.
    - Time Complexity:
        - General Networks: O(V^2 * E)
        - Unit Networks / Bipartite Matching: O(E * sqrt(V)) or O(E * V^(2/3))
    - Space Complexity: O(V + E) auxiliary space.

Supported Edge Cases:
    - Multi-edges (parallel edges between identical node pairs).
    - Antiparallel (bidirectional) edges.
    - Self-loops (u == v) and zero / negative capacity edges.
    - Disconnected source and sink components.
    - Source == Sink boundary conditions.
    - Deep layered / chain graphs (V up to thousands) without stack overflow.
"""

from __future__ import annotations

import sys


def max_flow(n: int, edges: list[tuple[int, int, int]], source: int, sink: int) -> int:
    """
    Computes the maximum network flow from source to sink in a directed graph.

    :param n: Number of vertices (labeled 0 to n - 1).
    :param edges: List of tuples (u, v, capacity) representing directed edges with integer capacities.
    :param source: Index of source node.
    :param sink: Index of sink node.
    :return: Maximum flow value as an integer.
    """
    # Boundary and edge case checks
    if n <= 1 or source == sink or source < 0 or source >= n or sink < 0 or sink >= n:
        return 0

    # Ensure recursion depth is sufficient for deep layered networks
    if sys.getrecursionlimit() < n + 100:
        try:
            sys.setrecursionlimit(n + 100)
        except (ValueError, RecursionError):
            pass

    # Build adjacency structure and residual edge arrays
    # Forward edges have even indices (2*k), reverse edges have odd indices (2*k + 1)
    adj: list[list[int]] = [[] for _ in range(n)]
    to: list[int] = []
    cap: list[int] = []

    for u, v, c in edges:
        # Ignore non-positive capacities, self-loops, or out-of-bounds node indices
        if c <= 0 or u == v or u < 0 or u >= n or v < 0 or v >= n:
            continue

        e = len(to)
        # Forward edge: u -> v with capacity c
        to.append(v)
        cap.append(c)
        adj[u].append(e)

        # Reverse residual edge: v -> u with initial capacity 0
        to.append(u)
        cap.append(0)
        adj[v].append(e + 1)

    total_flow = 0
    INF = 10**18  # Sentinel value representing infinite capacity

    # Reusable buffers for BFS and DFS
    level = [-1] * n
    ptr = [0] * n
    queue = [0] * n

    def dfs(u: int, pushed: int) -> int:
        """
        DFS to push blocking flow in the level graph.
        Uses current-arc optimization (ptr array) to avoid rescanning saturated edges.
        """
        if pushed == 0 or u == sink:
            return pushed

        tr = 0
        adj_u = adj[u]
        p = ptr[u]
        l_next = level[u] + 1

        while p < len(adj_u):
            e = adj_u[p]
            c = cap[e]
            v = to[e]

            # Only traverse admissible edges in the layered level graph
            if level[v] == l_next and c > 0:
                rem = pushed - tr
                push = dfs(v, min(c, rem))
                if push > 0:
                    cap[e] -= push
                    cap[e ^ 1] += push
                    tr += push
                    if tr == pushed:
                        break
            p += 1

        ptr[u] = p
        # If node u cannot satisfy the requested flow, all reachable paths from u
        # in the current level graph are exhausted. Mark as dead end.
        if tr < pushed:
            level[u] = -1

        return tr

    # Main Dinic loop: repeatedly construct level graphs via BFS
    while True:
        # Reset levels and current-arc pointers
        for i in range(n):
            level[i] = -1
            ptr[i] = 0

        level[source] = 0
        queue[0] = source
        head = 0
        tail = 1

        # Breadth-First Search to construct the level graph
        while head < tail:
            u = queue[head]
            head += 1
            l_next = level[u] + 1
            for e in adj[u]:
                v = to[e]
                if cap[e] > 0 and level[v] < 0:
                    level[v] = l_next
                    queue[tail] = v
                    tail += 1

        # If sink is unreachable in the residual network, no more augmenting paths exist
        if level[sink] < 0:
            break

        # Push blocking flows until no more flow can reach sink in this level graph
        while True:
            pushed = dfs(source, INF)
            if pushed == 0:
                break
            total_flow += pushed

    return total_flow


class DinicMaxFlow:
    """
    Object-oriented wrapper and utility class for Dinic's Algorithm.
    Useful for interactive graph construction, multiple queries, and competitive interfaces.
    """

    def __init__(self, n: int) -> None:
        self.n = n
        self.edges: list[tuple[int, int, int]] = []

    def add_edge(self, u: int, v: int, capacity: int) -> None:
        """Adds a directed edge from u to v with specified capacity."""
        self.edges.append((u, v, capacity))

    def compute_max_flow(self, source: int, sink: int) -> int:
        """Computes the maximum flow from source to sink."""
        return max_flow(self.n, self.edges, source, sink)


# LeetCode / competitive programming standard alias
Solution = DinicMaxFlow


def main() -> None:
    """CLI and self-test verification runner."""
    # Check if input is piped via stdin: standard competitive format
    # Line 1: n, m, source, sink
    # Next m lines: u, v, capacity
    if not sys.stdin.isatty():
        input_data = sys.stdin.read().split()
        if input_data:
            n = int(input_data[0])
            m = int(input_data[1])
            s = int(input_data[2])
            t = int(input_data[3])
            edges: list[tuple[int, int, int]] = []
            idx = 4
            for _ in range(m):
                u = int(input_data[idx])
                v = int(input_data[idx + 1])
                c = int(input_data[idx + 2])
                edges.append((u, v, c))
                idx += 3
            result = max_flow(n, edges, s, t)
            print(result)
            return

    # Default self-test demonstration
    print("=" * 70)
    print("Maximum Flow - Dinic's Algorithm with Current-Arc Optimization")
    print("=" * 70)

    # Classic network flow example
    n = 6
    sample_edges = [
        (0, 1, 10),
        (0, 2, 10),
        (1, 2, 2),
        (1, 3, 4),
        (1, 4, 8),
        (2, 4, 9),
        (3, 5, 10),
        (4, 3, 6),
        (4, 5, 10),
    ]
    flow = max_flow(n, sample_edges, 0, 5)
    print(f"Nodes: {n}, Source: 0, Sink: 5")
    print(f"Edges: {sample_edges}")
    print(f"Computed Maximum Flow: {flow}")
    assert flow == 19, f"Expected 19, got {flow}"
    print("Self-test PASSED successfully!")


if __name__ == "__main__":
    main()
