from collections import deque


def shortest_path_length(graph: list[list[int]]) -> int:
    """
    You have an undirected, connected graph of n nodes labeled from 0 to n - 1.
    You are given an array graph where graph[i] is a list of all the nodes connected with node i by an edge.
    Return the length of the shortest path that visits every node. You may start and stop at any node,
    you may revisit nodes multiple times, and you may reuse edges.
    """
    n = len(graph)
    if n <= 1:
        return 0

    target = (1 << n) - 1
    visited = [[False] * (1 << n) for _ in range(n)]

    queue = deque()
    for i in range(n):
        mask = 1 << i
        visited[i][mask] = True
        queue.append((i, mask, 0))

    while queue:
        u, mask, dist = queue.popleft()

        next_dist = dist + 1
        for v in graph[u]:
            next_mask = mask | (1 << v)
            if next_mask == target:
                return next_dist

            if not visited[v][next_mask]:
                visited[v][next_mask] = True
                queue.append((v, next_mask, next_dist))

    return 0
