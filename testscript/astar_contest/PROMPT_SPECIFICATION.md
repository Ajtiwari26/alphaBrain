Write a production-grade, highly optimized Python implementation of the A* Shortest Path Algorithm for a 2D weighted grid.

Save your implementation into a single standalone file named `astar_solver.py`.

### Target Function Signature
```python
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
```

### Specifications & Requirements
1. **Grid Representation**:
   - `grid` is a 2D list of integers `grid[row][col]`.
   - `grid[r][c] == -1` represents an impassable wall/obstacle.
   - `grid[r][c] >= 0` represents passable terrain, where the value is the traversal cost to step into cell `(r, c)`.
2. **Movement Costs**:
   - Cost of entering cell `(r_next, c_next)` orthogonally: `grid[r_next][c_next] * 1.0`.
   - Cost of entering cell `(r_next, c_next)` diagonally: `grid[r_next][c_next] * math.sqrt(2)`.
   - Initial starting cell cost is `0.0` (entering the starting cell incurs no traversal penalty).
3. **Corner-Cutting Prevention**:
   - When `allow_diagonal=True` and `prevent_corner_cutting=True`:
     A diagonal step from `(r, c)` to `(r+dr, c+dc)` is forbidden if either orthogonal neighbor `(r+dr, c)` or `(r, c+dc)` is an obstacle (`-1`).
   - When `prevent_corner_cutting=False`, diagonal passage between diagonally touching obstacles is allowed as long as the target cell itself is passable.
4. **Boundary & Error Conditions**:
   - If `start` or `goal` is out of bounds, return `(None, float('inf'))`.
   - If `start` or `goal` is an obstacle (`-1`), return `(None, float('inf'))`.
   - If `start == goal`: return `([start], 0.0)`.
   - If no connected path exists from `start` to `goal`, return `(None, float('inf'))`.
5. **Admissible Heuristic & Tie-Breaking**:
   - Use an admissible and consistent heuristic (e.g. Octile distance when diagonal is allowed, Manhattan distance when diagonal is disabled).
   - In the open set priority queue, break ties deterministically: prefer higher `g_score` (closer to goal), then smaller row `r`, then smaller column `c`.
6. **Efficiency**:
   - Must handle large grids ($100 \times 100$ or larger) with minimal memory allocation, fast heap operations, and early termination.
   - Use standard library only (`heapq`, `math`, `typing`).

Output ONLY the complete Python code in `astar_solver.py` without markdown backticks or commentary so it can be written directly to file.
