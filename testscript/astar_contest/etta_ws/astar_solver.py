from __future__ import annotations

import heapq
import math

SQRT2 = math.sqrt(2)
SQRT2_MINUS_ONE = SQRT2 - 1.0


def find_shortest_path(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    allow_diagonal: bool = True,
    prevent_corner_cutting: bool = True,
) -> tuple[list[tuple[int, int]] | None, float]:
    """
    Find the shortest path from start to goal on a 2D weighted grid using A* search.

    Returns:
        (path, total_cost)
        - path: list of (row, col) tuples from start to goal inclusive. If no path exists, return None.
        - total_cost: float representing total path cost. If no path exists, return float('inf').
    """
    if not grid or not grid[0]:
        return (None, float('inf'))

    rows = len(grid)
    cols = len(grid[0])

    sr, sc = start
    gr, gc = goal

    # Boundary validation
    if not (0 <= sr < rows and 0 <= sc < cols):
        return (None, float('inf'))
    if not (0 <= gr < rows and 0 <= gc < cols):
        return (None, float('inf'))

    # Obstacle validation
    if grid[sr][sc] == -1 or grid[gr][gc] == -1:
        return (None, float('inf'))

    # Trivial case: start is goal
    if sr == gr and sc == gc:
        return ([(sr, sc)], 0.0)

    # Initialize distance and parent tracking
    g_score = [[float('inf')] * cols for _ in range(rows)]
    parent = [[None] * cols for _ in range(rows)]

    g_score[sr][sc] = 0.0

    # Initial heuristic calculation
    dr = abs(sr - gr)
    dc = abs(sc - gc)
    if allow_diagonal:
        h_start = SQRT2_MINUS_ONE * dr + dc if dr < dc else SQRT2_MINUS_ONE * dc + dr
    else:
        h_start = float(dr + dc)

    # Priority queue element structure: (f_score, -g_score, r, c)
    # Tie-breaking: smaller f, then higher g (closer to goal), then smaller r, then smaller c
    open_set = [(h_start, 0.0, sr, sc)]

    while open_set:
        f, neg_g, r, c = heapq.heappop(open_set)
        curr_g = -neg_g

        # Skip stale entries
        if curr_g > g_score[r][c]:
            continue

        # Target reached
        if r == gr and c == gc:
            path = []
            curr: tuple[int, int] | None = (gr, gc)
            while curr is not None:
                path.append(curr)
                curr = parent[curr[0]][curr[1]]
            path.reverse()
            return (path, curr_g)

        # 1. Orthogonal neighbor expansions
        for dr_o, dc_o in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr = r + dr_o
            nc = c + dc_o
            if 0 <= nr < rows and 0 <= nc < cols:
                weight = grid[nr][nc]
                if weight != -1:
                    tentative_g = curr_g + weight
                    if tentative_g < g_score[nr][nc]:
                        g_score[nr][nc] = tentative_g
                        parent[nr][nc] = (r, c)
                        dr_g = abs(nr - gr)
                        dc_g = abs(nc - gc)
                        if allow_diagonal:
                            h = SQRT2_MINUS_ONE * dr_g + dc_g if dr_g < dc_g else SQRT2_MINUS_ONE * dc_g + dr_g
                        else:
                            h = float(dr_g + dc_g)
                        heapq.heappush(open_set, (tentative_g + h, -tentative_g, nr, nc))

        # 2. Diagonal neighbor expansions
        if allow_diagonal:
            for dr_d, dc_d in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                nr = r + dr_d
                nc = c + dc_d
                if 0 <= nr < rows and 0 <= nc < cols:
                    weight = grid[nr][nc]
                    if weight != -1:
                        if prevent_corner_cutting:
                            if grid[r + dr_d][c] == -1 or grid[r][c + dc_d] == -1:
                                continue
                        tentative_g = curr_g + weight * SQRT2
                        if tentative_g < g_score[nr][nc]:
                            g_score[nr][nc] = tentative_g
                            parent[nr][nc] = (r, c)
                            dr_g = abs(nr - gr)
                            dc_g = abs(nc - gc)
                            h = SQRT2_MINUS_ONE * dr_g + dc_g if dr_g < dc_g else SQRT2_MINUS_ONE * dc_g + dr_g
                            heapq.heappush(open_set, (tentative_g + h, -tentative_g, nr, nc))

    return (None, float('inf'))
