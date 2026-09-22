import sys

def max_flow(n: int, edges: list[tuple[int, int, int]], source: int, sink: int) -> int:
    """
    Computes the maximum network flow from source to sink in a directed graph.
    :param n: Number of vertices (0 to n - 1).
    :param edges: List of tuples (u, v, capacity) representing directed edges with integer capacities.
    :param source: Index of source node.
    :param sink: Index of sink node.
    :return: Maximum flow value as an integer.
    """
    if source == sink or n <= 0 or source < 0 or source >= n or sink < 0 or sink >= n:
        return 0

    if sys.getrecursionlimit() < n + 1000:
        sys.setrecursionlimit(n + 1000)

    # Build adjacency list representation
    # Each edge is stored as a mutable list: [to_node, residual_capacity, reverse_edge_ref]
    graph = [[] for _ in range(n)]
    for u, v, c in edges:
        if u < 0 or u >= n or v < 0 or v >= n:
            continue
        if c < 0:
            c = 0
        e1 = [v, c, None]
        e2 = [u, 0, e1]
        e1[2] = e2
        graph[u].append(e1)
        graph[v].append(e2)

    level = [-1] * n
    ptr = [0] * n

    def bfs() -> bool:
        for i in range(n):
            level[i] = -1
        level[source] = 0
        q = [source]
        q_ptr = 0
        while q_ptr < len(q):
            u = q[q_ptr]
            q_ptr += 1
            for edge in graph[u]:
                v = edge[0]
                if edge[1] > 0 and level[v] == -1:
                    level[v] = level[u] + 1
                    q.append(v)
        return level[sink] != -1

    def dfs(u: int, pushed: int) -> int:
        if pushed == 0 or u == sink:
            return pushed

        flow = 0
        gu = graph[u]
        n_edges = len(gu)

        while ptr[u] < n_edges:
            i = ptr[u]
            edge = gu[i]
            v = edge[0]
            c = edge[1]

            if level[v] == level[u] + 1 and c > 0:
                limit = pushed if pushed < c else c
                tr = dfs(v, limit)
                if tr > 0:
                    edge[1] -= tr
                    edge[2][1] += tr
                    flow += tr
                    pushed -= tr

                if tr < limit or edge[1] == 0:
                    ptr[u] = i + 1
                    if pushed == 0:
                        break
                    continue
                else:
                    break

            ptr[u] = i + 1

        if flow == 0:
            level[u] = -1
        return flow

    INF = float('inf')
    total_flow = 0
    while bfs():
        for i in range(n):
            ptr[i] = 0
        while True:
            pushed = dfs(source, INF)
            if pushed == 0:
                break
            total_flow += pushed

    return int(total_flow)
