"""
Shortest Path Visiting All Nodes (LeetCode 847)

Production-grade, highly optimized Python implementation of Shortest Path Visiting All Nodes
running in O(n^2 * 2^n) time using Multi-Source Breadth-First Search (BFS) over a bitmask state space.
"""

from __future__ import annotations

import collections
import sys


def shortest_path_length(graph: list[list[int]]) -> int:
    """
    You have an undirected, connected graph of n nodes labeled from 0 to n - 1.
    You are given an array graph where graph[i] is a list of all the nodes connected with node i by an edge.
    Return the length of the shortest path that visits every node. You may start and stop at any node,
    you may revisit nodes multiple times, and you may reuse edges.
    """
    n = len(graph)
    # Trivial base cases: 0 or 1 node requires 0 steps
    if n <= 1:
        return 0

    target_mask = (1 << n) - 1

    # Multi-source BFS initialization:
    # State is represented as (node, mask).
    # Since n <= 12, the total number of states is n * (1 << n) <= 12 * 4096 = 49,152.
    # We use a flat bytearray of size (n << n) for O(1) cache-friendly lookups without tuple/hash overhead.
    visited = bytearray(n << n)
    queue: collections.deque[tuple[int, int]] = collections.deque()

    for i in range(n):
        mask = 1 << i
        visited[(i << n) | mask] = 1
        queue.append((i, mask))

    steps = 0
    while queue:
        level_size = len(queue)
        for _ in range(level_size):
            u, mask = queue.popleft()

            for v in graph[u]:
                next_mask = mask | (1 << v)
                # Immediate goal check upon generating neighbor
                if next_mask == target_mask:
                    return steps + 1

                idx = (v << n) | next_mask
                if not visited[idx]:
                    visited[idx] = 1
                    queue.append((v, next_mask))

        steps += 1

    return -1


class Solution:
    """LeetCode compatible class wrapper for Shortest Path Visiting All Nodes (LeetCode 847)."""

    def shortestPathLength(self, graph: list[list[int]]) -> int:
        return shortest_path_length(graph)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json

        try:
            input_graph = json.loads(sys.argv[1])
            print(shortest_path_length(input_graph))
        except (json.JSONDecodeError, ValueError) as err:
            print(f"Error parsing CLI input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # Self-tests with canonical examples
        # Example 1: [[1,2,3],[0],[0],[0]] -> 4
        assert shortest_path_length([[1, 2, 3], [0], [0], [0]]) == 4, "Test 1 Failed"

        # Example 2: [[1],[0,2,4],[1,3,4],[2],[1,2]] -> 4
        assert shortest_path_length([[1], [0, 2, 4], [1, 3, 4], [2], [1, 2]]) == 4, "Test 2 Failed"

        # Single node test
        assert shortest_path_length([[]]) == 0, "Test Single Node Failed"

        # Two nodes connected
        assert shortest_path_length([[1], [0]]) == 1, "Test 2 Nodes Failed"

        # Complete graph K4
        assert shortest_path_length([[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]) == 3, "Test K4 Failed"

        print("Self-test passed successfully!")
