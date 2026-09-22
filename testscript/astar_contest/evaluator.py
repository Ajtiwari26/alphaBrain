"""
Blind Evaluation Harness for A* Shortest Path Challenge.
Contains 12 rigorous edge cases testing algorithmic correctness,
corner-cutting prevention, cost precision, and scalability.
"""

import math
import sys
import time
import importlib.util
from pathlib import Path


def load_solver(solver_path: Path):
    if not solver_path.exists():
        raise FileNotFoundError(f"Solver file not found: {solver_path}")
    spec = importlib.util.spec_from_file_location("astar_candidate", solver_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "find_shortest_path"):
        raise AttributeError(f"Module {solver_path} is missing find_shortest_path function")
    return module.find_shortest_path


def validate_path_integrity(grid, path, start, goal, allow_diagonal, prevent_corner_cutting, expected_cost):
    if path is None:
        return False, "Path is None"
    if not path:
        return False, "Path is empty"
    if path[0] != start:
        return False, f"Path does not start at {start}, starts at {path[0]}"
    if path[-1] != goal:
        return False, f"Path does not end at {goal}, ends at {path[-1]}"

    calculated_cost = 0.0
    rows = len(grid)
    cols = len(grid[0])

    for i in range(len(path) - 1):
        curr = path[i]
        nxt = path[i + 1]
        r1, c1 = curr
        r2, c2 = nxt

        dr = abs(r2 - r1)
        dc = abs(c2 - c1)

        if dr > 1 or dc > 1 or (dr == 0 and dc == 0):
            return False, f"Invalid step from {curr} to {nxt}"

        if not (0 <= r2 < rows and 0 <= c2 < cols):
            return False, f"Step {nxt} is out of bounds"

        cell_val = grid[r2][c2]
        if cell_val == -1:
            return False, f"Step {nxt} moved into obstacle (-1)"

        if dr == 1 and dc == 1:
            if not allow_diagonal:
                return False, f"Diagonal move from {curr} to {nxt} taken when allow_diagonal=False"
            if prevent_corner_cutting:
                # Check orthogonal neighbors
                if grid[r1][c2] == -1 or grid[r2][c1] == -1:
                    return False, f"Corner cutting violated moving from {curr} to {nxt}"
            calculated_cost += cell_val * math.sqrt(2)
        else:
            calculated_cost += cell_val * 1.0

    if abs(calculated_cost - expected_cost) > 1e-4:
        return False, f"Calculated cost {calculated_cost:.4f} does not match returned cost {expected_cost:.4f}"

    return True, "Valid"


def run_test_suite(find_shortest_path):
    results = []

    # -------------------------------------------------------------
    # Case 1: Immediate Match (Start == Goal) on High-Cost Cell
    # -------------------------------------------------------------
    try:
        grid1 = [[10, 20], [30, 40]]
        path, cost = find_shortest_path(grid1, (1, 1), (1, 1))
        assert path == [(1, 1)], f"Expected [(1, 1)], got {path}"
        assert abs(cost - 0.0) < 1e-5, f"Start cost must be 0.0, got {cost}"
        results.append((1, "Immediate Match (Start == Goal)", True, None))
    except Exception as e:
        results.append((1, "Immediate Match (Start == Goal)", False, str(e)))

    # -------------------------------------------------------------
    # Case 2: Hermetic Obstacle Enclosure (Completely Trapped Goal)
    # -------------------------------------------------------------
    try:
        grid2 = [
            [1,  1,  1,  1, 1],
            [1, -1, -1, -1, 1],
            [1, -1,  5, -1, 1],
            [1, -1, -1, -1, 1],
            [1,  1,  1,  1, 1],
        ]
        path, cost = find_shortest_path(grid2, (0, 0), (2, 2))
        assert path is None, f"Enclosed goal must return None path, got {path}"
        assert math.isinf(cost), f"Enclosed goal must return infinite cost, got {cost}"
        results.append((2, "Hermetic Obstacle Enclosure", True, None))
    except Exception as e:
        results.append((2, "Hermetic Obstacle Enclosure", False, str(e)))

    # -------------------------------------------------------------
    # Case 3: Corner-Cutting Squeeze Prevention
    # -------------------------------------------------------------
    try:
        grid3 = [
            [1, -1],
            [-1, 1],
        ]
        # With corner-cutting prevented, diagonal from (0,0) to (1,1) is illegal
        path_blocked, cost_blocked = find_shortest_path(
            grid3, (0, 0), (1, 1), allow_diagonal=True, prevent_corner_cutting=True
        )
        assert path_blocked is None and math.isinf(cost_blocked), (
            f"Corner-cutting move must be blocked, got {path_blocked}, {cost_blocked}"
        )

        # With corner-cutting allowed, diagonal from (0,0) to (1,1) is legal
        path_allowed, cost_allowed = find_shortest_path(
            grid3, (0, 0), (1, 1), allow_diagonal=True, prevent_corner_cutting=False
        )
        assert path_allowed == [(0, 0), (1, 1)], f"Expected [(0,0), (1,1)], got {path_allowed}"
        assert abs(cost_allowed - math.sqrt(2)) < 1e-4, f"Expected sqrt(2), got {cost_allowed}"
        results.append((3, "Corner-Cutting Squeeze Prevention", True, None))
    except Exception as e:
        results.append((3, "Corner-Cutting Squeeze Prevention", False, str(e)))

    # -------------------------------------------------------------
    # Case 4: Cost-Weight Inversion (Paved Detour vs Swamp Shortcut)
    # -------------------------------------------------------------
    try:
        # Straight line row 2 costs 30 each cell (30*3 + 1 = 91).
        # Detour along row 0 costs 1 each cell (8 steps = 8.0).
        grid4 = [
            [1,  1,  1,  1, 1],
            [1, -1, -1, -1, 1],
            [1, 30, 30, 30, 1],
            [1, -1, -1, -1, 1],
            [1,  1,  1,  1, 1],
        ]
        path, cost = find_shortest_path(grid4, (2, 0), (2, 4), allow_diagonal=False)
        valid, msg = validate_path_integrity(grid4, path, (2, 0), (2, 4), False, True, cost)
        assert valid, msg
        # Expected detour: (2,0)->(1,0)->(0,0)->(0,1)->(0,2)->(0,3)->(0,4)->(1,4)->(2,4) = 8 steps of cost 1 = 8.0
        assert abs(cost - 8.0) < 1e-4, f"Expected detour cost 8.0, got {cost}"
        results.append((4, "Cost-Weight Inversion (Paved Detour)", True, None))
    except Exception as e:
        results.append((4, "Cost-Weight Inversion (Paved Detour)", False, str(e)))

    # -------------------------------------------------------------
    # Case 5: Zero-Cost Neutral Plateau without Infinite Cycling
    # -------------------------------------------------------------
    try:
        grid5 = [
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]
        path, cost = find_shortest_path(grid5, (0, 0), (0, 4), allow_diagonal=False)
        valid, msg = validate_path_integrity(grid5, path, (0, 0), (0, 4), False, True, cost)
        assert valid, msg
        # (0,0) -> (0,1)[0] -> (0,2)[0] -> (0,3)[0] -> (0,4)[1] = cost 1.0
        assert abs(cost - 1.0) < 1e-4, f"Expected zero-plateau cost 1.0, got {cost}"
        results.append((5, "Zero-Cost Neutral Plateau", True, None))
    except Exception as e:
        results.append((5, "Zero-Cost Neutral Plateau", False, str(e)))

    # -------------------------------------------------------------
    # Case 6: Deep Concave Cul-de-Sac (U-Trap Local Minimum)
    # -------------------------------------------------------------
    try:
        # 7x7 grid with U opening to the left (West). Start at (3, 3) inside cup.
        # Goal at (3, 6) right behind the right wall of the cup.
        grid6 = [
            [1,  1,  1,  1,  1,  1, 1],
            [1, -1, -1, -1, -1,  1, 1],
            [1, -1,  1,  1, -1,  1, 1],
            [1,  1,  1,  1, -1,  1, 1],
            [1, -1,  1,  1, -1,  1, 1],
            [1, -1, -1, -1, -1,  1, 1],
            [1,  1,  1,  1,  1,  1, 1],
        ]
        # Start at (3, 2), Goal at (3, 6)
        path, cost = find_shortest_path(grid6, (3, 2), (3, 6), allow_diagonal=True, prevent_corner_cutting=True)
        valid, msg = validate_path_integrity(grid6, path, (3, 2), (3, 6), True, True, cost)
        assert valid, msg
        assert path is not None and not math.isinf(cost), "Should successfully escape U-trap"
        results.append((6, "Deep Concave Cul-de-Sac (U-Trap)", True, None))
    except Exception as e:
        results.append((6, "Deep Concave Cul-de-Sac (U-Trap)", False, str(e)))

    # -------------------------------------------------------------
    # Case 7: Blocked Start or Goal (-1 Cell)
    # -------------------------------------------------------------
    try:
        grid7 = [
            [-1, 1, 1],
            [ 1, 1, 1],
            [ 1, 1, -1],
        ]
        p1, c1 = find_shortest_path(grid7, (0, 0), (1, 1))
        assert p1 is None and math.isinf(c1), "Blocked start must return None, inf"
        p2, c2 = find_shortest_path(grid7, (1, 1), (2, 2))
        assert p2 is None and math.isinf(c2), "Blocked goal must return None, inf"
        results.append((7, "Blocked Start or Goal (-1 Cell)", True, None))
    except Exception as e:
        results.append((7, "Blocked Start or Goal (-1 Cell)", False, str(e)))

    # -------------------------------------------------------------
    # Case 8: Out-of-Bounds Start or Goal
    # -------------------------------------------------------------
    try:
        grid8 = [[1, 1], [1, 1]]
        p1, c1 = find_shortest_path(grid8, (-1, 0), (1, 1))
        assert p1 is None and math.isinf(c1), "Negative start coord must return None, inf"
        p2, c2 = find_shortest_path(grid8, (0, 0), (5, 5))
        assert p2 is None and math.isinf(c2), "Out of bounds goal must return None, inf"
        results.append((8, "Out-of-Bounds Coordinates", True, None))
    except Exception as e:
        results.append((8, "Out-of-Bounds Coordinates", False, str(e)))

    # -------------------------------------------------------------
    # Case 9: Diagonal Disabled Flag Enforcement
    # -------------------------------------------------------------
    try:
        grid9 = [
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
        ]
        path, cost = find_shortest_path(grid9, (0, 0), (2, 2), allow_diagonal=False)
        valid, msg = validate_path_integrity(grid9, path, (0, 0), (2, 2), False, True, cost)
        assert valid, msg
        # In 4-directional, Manhattan distance is 4 steps of cost 1 = 4.0
        assert abs(cost - 4.0) < 1e-4, f"Expected Manhattan cost 4.0, got {cost}"
        for i in range(len(path) - 1):
            dr = abs(path[i+1][0] - path[i][0])
            dc = abs(path[i+1][1] - path[i][1])
            assert not (dr == 1 and dc == 1), f"Diagonal step detected when allow_diagonal=False: {path[i]}->{path[i+1]}"
        results.append((9, "Diagonal Disabled Flag Enforcement", True, None))
    except Exception as e:
        results.append((9, "Diagonal Disabled Flag Enforcement", False, str(e)))

    # -------------------------------------------------------------
    # Case 10: Degenerate Grids (1x1 and 1xN with Mid-Barrier)
    # -------------------------------------------------------------
    try:
        # 1x1 grid
        grid10a = [[7]]
        pa, ca = find_shortest_path(grid10a, (0, 0), (0, 0))
        assert pa == [(0, 0)] and abs(ca - 0.0) < 1e-5, f"1x1 degenerate grid failed: {pa}, {ca}"

        # 1x5 corridor with wall in middle
        grid10b = [[1, 1, -1, 1, 1]]
        pb, cb = find_shortest_path(grid10b, (0, 0), (0, 4))
        assert pb is None and math.isinf(cb), f"1xN corridor wall bypass impossible: {pb}, {cb}"
        results.append((10, "Degenerate Grids (1x1 and 1xN)", True, None))
    except Exception as e:
        results.append((10, "Degenerate Grids (1x1 and 1xN)", False, str(e)))

    # -------------------------------------------------------------
    # Case 11: Subpath Cost Revision (Re-Opening / Cheaper Path)
    # -------------------------------------------------------------
    try:
        # Direct diagonal (0,0) -> (1,1) costs 10 * sqrt(2) = 14.142
        # Alternative path (0,0) -> (0,1)[cost 1] -> (1,1)[cost 1] = 2.0
        grid11 = [
            [1, 1],
            [1, 10],
        ]
        # In grid11, to reach (1, 1):
        # Orthogonal via (0, 1) or (1, 0) into (1, 1) costs: 1 + 10 = 11.0
        # Diagonal from (0, 0) into (1, 1) costs: 10 * sqrt(2) = 14.142
        # A* must pick orthogonal (cost 11.0) instead of diagonal (14.142)
        path, cost = find_shortest_path(grid11, (0, 0), (1, 1), allow_diagonal=True, prevent_corner_cutting=True)
        valid, msg = validate_path_integrity(grid11, path, (0, 0), (1, 1), True, True, cost)
        assert valid, msg
        assert abs(cost - 11.0) < 1e-4, f"Expected cheaper orthogonal subpath 11.0, got {cost}"
        assert len(path) == 3, f"Expected 3-node path, got {len(path)}: {path}"
        results.append((11, "Subpath Cost Revision", True, None))
    except Exception as e:
        results.append((11, "Subpath Cost Revision", False, str(e)))

    # -------------------------------------------------------------
    # Case 12: High-Density 100x100 Labyrinth Stress Test
    # -------------------------------------------------------------
    try:
        # Deterministic 100x100 grid
        size = 100
        grid12 = [[1 for _ in range(size)] for _ in range(size)]
        # Add alternating serpentine barriers
        for r in range(10, size - 10, 10):
            if (r // 10) % 2 == 1:
                for c in range(0, size - 15):
                    grid12[r][c] = -1
            else:
                for c in range(15, size):
                    grid12[r][c] = -1

        t0 = time.perf_counter()
        path, cost = find_shortest_path(grid12, (0, 0), (size - 1, size - 1), allow_diagonal=True, prevent_corner_cutting=True)
        elapsed = time.perf_counter() - t0

        valid, msg = validate_path_integrity(grid12, path, (0, 0), (size - 1, size - 1), True, True, cost)
        assert valid, f"Labyrinth invalid: {msg}"
        assert elapsed < 2.0, f"Performance issue: took {elapsed:.3f}s (budget: 2.0s)"
        results.append((12, f"100x100 Labyrinth Stress Test ({elapsed*1000:.1f}ms)", True, None))
    except Exception as e:
        results.append((12, "100x100 Labyrinth Stress Test", False, str(e)))

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluator.py <path_to_astar_solver.py>")
        sys.exit(1)

    solver_file = Path(sys.argv[1])
    try:
        solver_fn = load_solver(solver_file)
    except Exception as e:
        print(f"FAILED TO LOAD SOLVER: {e}")
        sys.exit(1)

    print(f"\n=======================================================================")
    print(f"  BLIND EVALUATION: {solver_file.name} ({solver_file.parent.name})")
    print(f"=======================================================================")

    t_start = time.perf_counter()
    test_results = run_test_suite(solver_fn)
    total_time = (time.perf_counter() - t_start) * 1000.0

    passed_count = sum(1 for _, _, ok, _ in test_results if ok)
    total_count = len(test_results)

    for num, name, ok, err in test_results:
        status_str = "PASS" if ok else "FAIL"
        glyph = "OK " if ok else "ERR"
        print(f"[{glyph}] Case {num:02d}: {name:<42} -> {status_str}")
        if not ok and err:
            print(f"      └─ Error: {err}")

    print(f"-----------------------------------------------------------------------")
    print(f"SCORE: {passed_count}/{total_count} Passed | Total Execution Time: {total_time:.2f}ms")
    print(f"=======================================================================\n")

    sys.exit(0 if passed_count == total_count else 2)
