from __future__ import annotations

import heapq
import math


def find_shortest_path(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    allow_diagonal: bool = True,
    prevent_corner_cutting: bool = True,
) -> tuple[list[tuple[int, int]] | None, float]:
    """
    Find the shortest path from start to goal on a 2D weighted grid using A* search.

    Args:
        grid: 2D list of integers. -1 represents an impassable wall/obstacle.
              Values >= 0 represent passable terrain where the value is the
              traversal cost to step into that cell.
        start: (row, col) coordinates of the starting cell.
        goal: (row, col) coordinates of the goal cell.
        allow_diagonal: If True, allows 8-directional movement. If False, allows
                        only 4-directional (orthogonal) movement.
        prevent_corner_cutting: If True and allow_diagonal is True, diagonal movement
                                between obstacles is forbidden if either orthogonal
                                adjacent cell is an obstacle (-1).

    Returns:
        (path, total_cost)
        - path: list of (row, col) tuples from start to goal inclusive.
                If no path exists, returns None.
        - total_cost: float representing total path cost.
                      If no path exists, returns float('inf').
    """
    # 1. Boundary & Empty Grid Validation
    if not grid or not grid[0]:
        return None, float("inf")

    rows = len(grid)
    cols = len(grid[0])
    sr, sc = start
    gr, gc = goal

    # Validate start and goal are within grid boundaries
    if not (0 <= sr < rows and 0 <= sc < cols):
        return None, float("inf")
    if not (0 <= gr < rows and 0 <= gc < cols):
        return None, float("inf")

    # Validate start and goal are passable cells
    if grid[sr][sc] == -1 or grid[gr][gc] == -1:
        return None, float("inf")

    # Start equals goal: trivially reachable with zero additional cost
    if start == goal:
        return [start], 0.0

    # 2. Heuristic Setup (Admissible & Consistent)
    sqrt2 = math.sqrt(2.0)
    sqrt2_minus_1 = sqrt2 - 1.0

    if allow_diagonal:
        # Octile Distance: D1 * (max - min) + D2 * min = max + (sqrt(2) - 1) * min
        def heuristic(r: int, c: int) -> float:
            dr = abs(r - gr)
            dc = abs(c - gc)
            return (dr if dr > dc else dc) + sqrt2_minus_1 * (dc if dr > dc else dr)
    else:
        # Manhattan Distance: abs(dr) + abs(dc)
        def heuristic(r: int, c: int) -> float:
            return float(abs(r - gr) + abs(c - gc))

    # 3. Direction Vectors
    orthogonal_dirs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    diagonal_dirs = ((-1, -1), (-1, 1), (1, -1), (1, 1))

    # 4. Open Set Priority Queue & State Tracking
    # Open set tuple: (f_score, -g_score, row, col)
    # Tie-breaking rules:
    #   1. Smallest f_score
    #   2. Largest g_score (closer to goal), achieved via smaller -g_score
    #   3. Smallest row r
    #   4. Smallest column c
    h_start = heuristic(sr, sc)
    open_set: list[tuple[float, float, int, int]] = [(h_start, -0.0, sr, sc)]

    g_score: dict[tuple[int, int], float] = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}

    while open_set:
        f, neg_g, r, c = heapq.heappop(open_set)
        curr_g = -neg_g

        # Skip stale entries in the heap
        if curr_g > g_score[(r, c)]:
            continue

        # Early termination upon reaching the goal
        if (r, c) == goal:
            path: list[tuple[int, int]] = []
            curr: tuple[int, int] | None = goal
            while curr is not None:
                path.append(curr)
                curr = came_from.get(curr)
            path.reverse()
            return path, g_score[goal]

        # 5. Expand Orthogonal Neighbors
        for dr, dc in orthogonal_dirs:
            nr = r + dr
            nc = c + dc

            if 0 <= nr < rows and 0 <= nc < len(grid[nr]):
                cell_cost = grid[nr][nc]
                if cell_cost == -1:
                    continue

                tentative_g = curr_g + float(cell_cost)
                neighbor = (nr, nc)

                if tentative_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g
                    came_from[neighbor] = (r, c)
                    h_val = heuristic(nr, nc)
                    heapq.heappush(
                        open_set,
                        (tentative_g + h_val, -tentative_g, nr, nc),
                    )

        # 6. Expand Diagonal Neighbors (if enabled)
        if allow_diagonal:
            for dr, dc in diagonal_dirs:
                nr = r + dr
                nc = c + dc

                if 0 <= nr < rows and 0 <= nc < len(grid[nr]):
                    cell_cost = grid[nr][nc]
                    if cell_cost == -1:
                        continue

                    # Corner-cutting check: diagonal step is forbidden if either
                    # orthogonal adjacent neighbor is an obstacle (-1)
                    if prevent_corner_cutting:
                        if grid[r + dr][c] == -1 or grid[r][c + dc] == -1:
                            continue

                    tentative_g = curr_g + cell_cost * sqrt2
                    neighbor = (nr, nc)

                    if tentative_g < g_score.get(neighbor, float("inf")):
                        g_score[neighbor] = tentative_g
                        came_from[neighbor] = (r, c)
                        h_val = heuristic(nr, nc)
                        heapq.heappush(
                            open_set,
                            (tentative_g + h_val, -tentative_g, nr, nc),
                        )

    return None, float("inf")
