#!/usr/bin/env python3
"""
Setup script for 10 Hardest Algorithmic Problems (Decathlon Benchmark).
Generates PROMPT.md and evaluator.py for each problem.
"""

import sys
from pathlib import Path

DECATHLON_ROOT = Path(__file__).parent.resolve()

# ==============================================================================
# PROBLEM 01: LeetCode 3013 (Divide an Array Into Subarrays With Minimum Cost II)
# ==============================================================================
P01_DIR = DECATHLON_ROOT / "problem01_subarrays_cost"
P01_PROMPT = """Write a production-grade, highly optimized Python implementation of Divide an Array Into Subarrays With Minimum Cost II (LeetCode 3013).

Save your implementation into a single standalone file named `minimum_cost.py`.

### Target Function Signature
```python
def minimum_cost(nums: list[int], k: int, dist: int) -> int:
    \"\"\"
    You are given an integer array nums of length n, and two integers k and dist.
    You must divide nums into k contiguous subarrays.
    The cost of dividing nums is the sum of the first elements of each of the k subarrays.
    The first element of the first subarray is always nums[0].
    The distance between the start index of the second subarray and the start index of the
    k-th subarray must be at most dist. That is, if the start indices of the subarrays are
    0 = i_0 < i_1 < i_2 < ... < i_{k-1}, then i_{k-1} - i_1 <= dist.
    Return the minimum possible cost.
    \"\"\"
```

### Specifications & Complexity
- Equivalent to finding index 0, plus the minimum sum of (k - 1) elements within any sliding window of size `dist` starting from index 1 to n - 1.
- Must run in $O(N \log N)$ or $O(N \log dist)$ time using dual heaps/multisets with lazy deletion, or a balanced tree.
- Any $O(N \cdot dist)$ approach will strictly TLE on $N = 20,000$.

Output ONLY the complete Python code in `minimum_cost.py` without markdown backticks or commentary so it can be written directly to file.
"""

P01_EVALUATOR = """import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p01", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.minimum_cost

def naive_min_cost(nums, k, dist):
    n = len(nums)
    needed = k - 1
    min_sum = float('inf')
    for i in range(1, n - needed + 1):
        win = nums[i : min(n, i + dist + 1)]
        if len(win) >= needed:
            s = sum(sorted(win)[:needed])
            if s < min_sum:
                min_sum = s
    return nums[0] + min_sum

random.seed(42)
S_NUMS = [random.randint(1, 1000) for _ in range(10000)]
S_K, S_DIST = 100, 500
S_EXP = naive_min_cost(S_NUMS, S_K, S_DIST)

CASES = [
    (1, "Standard Case 1", [1,3,2,6,4,2], 3, 3, 5),
    (2, "Standard Case 2", [10,1,2,2,2,1], 4, 3, 15),
    (3, "Minimal k=2", [10, 8, 3, 5, 2], 2, 2, 12),
    (4, "k equals array length", [1, 2, 3], 3, 2, 6),
    (5, "dist equals 1", [5, 4, 3, 2, 1], 3, 2, 10),
    (6, "Uniform identical elements", [7, 7, 7, 7, 7, 7], 3, 3, 21),
    (7, "Strictly increasing sequence", [1, 2, 3, 4, 5, 6, 7], 3, 3, 6),
    (8, "Strictly decreasing sequence", [10, 9, 8, 7, 6, 5], 4, 4, 28),
    (9, "Large distance window", [1, 10, 20, 30, 2, 3, 4], 4, 5, 10),
    (10, "Minimum valid window size", [5, 1, 2], 3, 2, 8),
    (11, "Large element values", [1000000, 500000, 200000, 800000], 3, 2, 1700000),
    (12, "Stress Test N=10,000, k=100", S_NUMS, S_K, S_DIST, S_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, *args in CASES:
        exp = args[-1]
        t0 = time.perf_counter()
        try:
            got = fn(*args[:-1])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and (num != 12 or elapsed < 2500):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 02: LeetCode 420 (Strong Password Checker)
# ==============================================================================
P02_DIR = DECATHLON_ROOT / "problem02_password_checker"
P02_PROMPT = """Write a production-grade, highly optimized Python implementation of Strong Password Checker (LeetCode 420).

Save your implementation into a single standalone file named `password_checker.py`.

### Target Function Signature
```python
def strong_password_checker(password: str) -> int:
    \"\"\"
    Calculate the minimum number of steps (insert, delete, replace) to make password strong:
    1. Length between 6 and 20.
    2. At least 1 lowercase, 1 uppercase, 1 digit.
    3. No three consecutive identical characters.
    \"\"\"
```

Output ONLY the complete Python code in `password_checker.py` without markdown backticks or commentary so it can be written directly to file.
"""

P02_EVALUATOR = """import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p02", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.strong_password_checker

CASES = [
    (1, "Empty String (Length 0)", "", 6),
    (2, "Single Char (Length 1)", "a", 5),
    (3, "Short String with Categories", "aA1", 3),
    (4, "Already Strong Password", "1337C0d3", 0),
    (5, "Short String with 3-Repeat", "aaa", 3),
    (6, "Length 6 Full Repeat", "aaaaaa", 2),
    (7, "Length 6 Dual Repeats", "aaa111", 2),
    (8, "Length 10 All Digits", "1111111111", 3),
    (9, "Length 21 Monolithic Repeat", "aaaaaaaaaaaaaaaaaaaaa", 7),
    (10, "Length 21 Multi-Repeat Modulo Interplay", "bbaaaaaaaaaaaaaaacccc", 6),
    (11, "Length 21 Alternating Missing Lowercase", "ABABABABABABABABABAB1", 2),
    (12, "Length 21 Monodigit with Prefix", "A12345678901234567890", 2),
    (13, "Length 5 Missing Upper and Digit", "aaaaa", 2),
    (14, "Length 20 Compliant With Single Repeat", "Abcdef1234567890aaaB", 1),
    (15, "Long Modulo-2 Cascade", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 13),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(inp)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp:
                print(f"[OK ] Case {num:02d}: {name:<40} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<40} ({elapsed:.2f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<40} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 03: LeetCode 887 (Super Egg Drop)
# ==============================================================================
P03_DIR = DECATHLON_ROOT / "problem03_egg_drop"
P03_PROMPT = """Write a production-grade, highly optimized Python implementation of Super Egg Drop (LeetCode 887).

Save your implementation into a single standalone file named `super_egg_drop.py`.

### Target Function Signature
```python
def super_egg_drop(k: int, n: int) -> int:
    \"\"\"
    You are given k identical eggs and you have access to a building with n floors labeled from 1 to n.
    You know that there exists a floor f where 0 <= f <= n such that any egg dropped at a floor higher than f
    will break, and any egg dropped at or below floor f will not break.
    Return the minimum number of moves that you need to determine with certainty what the value of f is.
    \"\"\"
```

### Specifications & Complexity
- Constraints: 1 <= k <= 100, 1 <= n <= 10^4.
- Must run in $O(K \log N)$ or inverted DP $O(K \cdot M)$ where $M$ is moves.
- Naive $O(K \cdot N^2)$ DP will strictly TLE.

Output ONLY the complete Python code in `super_egg_drop.py` without markdown backticks or commentary so it can be written directly to file.
"""

P03_EVALUATOR = """import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p03", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.super_egg_drop

CASES = [
    (1, "Single egg k=1, n=2", 1, 2, 2),
    (2, "k=2 eggs, n=6 floors", 2, 6, 3),
    (3, "k=3 eggs, n=14 floors", 3, 14, 4),
    (4, "Single floor n=1", 10, 1, 1),
    (5, "k=2 eggs, n=100 floors", 2, 100, 14),
    (6, "k=1 egg, n=100 floors", 1, 100, 100),
    (7, "k=4 eggs, n=50 floors", 4, 50, 6),
    (8, "k=5 eggs, n=200 floors", 5, 200, 9),
    (9, "k=10 eggs, n=1000 floors", 10, 1000, 11),
    (10, "k=3 eggs, n=26 floors", 3, 26, 5),
    (11, "k=7 eggs, n=5000 floors", 7, 5000, 14),
    (12, "Stress Test k=100, n=10,000", 100, 10000, 14),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, k, n, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(k, n)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and elapsed < 1000:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 04: LeetCode 354 (Russian Doll Envelopes)
# ==============================================================================
P04_DIR = DECATHLON_ROOT / "problem04_russian_dolls"
P04_PROMPT = """Write a production-grade, highly optimized Python implementation of Russian Doll Envelopes (LeetCode 354).

Save your implementation into a single standalone file named `russian_dolls.py`.

### Target Function Signature
```python
def max_envelopes(envelopes: list[list[int]]) -> int:
    \"\"\"
    You are given a 2D array of integers envelopes where envelopes[i] = [w_i, h_i] represents the width and height of an envelope.
    One envelope can fit into another if and only if both the width and height of one envelope are strictly greater than the other envelope.
    Return the maximum number of envelopes you can Russian doll (i.e., put one inside the other).
    Note: You cannot rotate an envelope.
    \"\"\"
```

### Specifications & Complexity
- Constraints: 1 <= envelopes.length <= 10^5.
- Must run in $O(N \log N)$ time (e.g. sorting by width asc, height desc, then patience sort/binary search LIS).
- Naive $O(N^2)$ DP will strictly TLE on large inputs.

Output ONLY the complete Python code in `russian_dolls.py` without markdown backticks or commentary so it can be written directly to file.
"""

P04_EVALUATOR = """import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p04", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.max_envelopes

random.seed(42)
S_ENV = [[random.randint(1, 100000), random.randint(1, 100000)] for _ in range(20000)]

CASES = [
    (1, "Standard Case", [[5,4],[6,4],[6,7],[2,3]], 3),
    (2, "All Identical Envelopes", [[1,1],[1,1],[1,1]], 1),
    (3, "Single Envelope", [[10, 20]], 1),
    (4, "Strict Telescoping Chain", [[1,1],[2,2],[3,3],[4,4],[5,5]], 5),
    (5, "Same Width Differing Heights", [[2,3],[2,4],[2,5]], 1),
    (6, "Same Height Differing Widths", [[3,2],[4,2],[5,2]], 1),
    (7, "Reverse Ordered Chain", [[5,5],[4,4],[3,3],[2,2],[1,1]], 5),
    (8, "Crossed Widths and Heights", [[1,5],[2,4],[3,3],[4,2],[5,1]], 1),
    (9, "Zigzag Dimensions", [[1,2],[2,1],[3,4],[4,3],[5,6]], 3),
    (10, "Empty Envelopes List", [], 0),
    (11, "Two Envelopes Nested", [[4,5],[4,6],[6,7],[2,3],[1,1]], 4),
    (12, "Stress Test N=20,000", S_ENV, None), # verified elapsed < 1.0s and returns int > 0
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn([list(x) for x in inp])
            elapsed = (time.perf_counter() - t0) * 1000.0
            ok = (got == exp) if exp is not None else (isinstance(got, int) and got > 0 and elapsed < 1000)
            if ok:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 05: LeetCode 218 (The Skyline Problem)
# ==============================================================================
P05_DIR = DECATHLON_ROOT / "problem05_skyline"
P05_PROMPT = """Write a production-grade, highly optimized Python implementation of The Skyline Problem (LeetCode 218).

Save your implementation into a single standalone file named `skyline.py`.

### Target Function Signature
```python
def get_skyline(buildings: list[list[int]]) -> list[list[int]]:
    \"\"\"
    Return the outer contour silhouette key points [x, y] sorted by x-coordinate.
    Consecutive points of equal height must be merged. Last point must end at height 0.
    \"\"\"
```

Output ONLY the complete Python code in `skyline.py` without markdown backticks or commentary so it can be written directly to file.
"""

P05_EVALUATOR = """import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p05", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.get_skyline

CASES = [
    (1, "Standard Multi-Building City", [[2,9,10],[3,7,15],[5,12,12],[15,20,10],[19,24,8]], [[2,10],[3,15],[7,12],[12,0],[15,10],[20,8],[24,0]]),
    (2, "Adjacent Equal-Height Buildings", [[0,2,3],[2,5,3]], [[0,3],[5,0]]),
    (3, "Identical Span Multiple Heights", [[1,2,1],[1,2,2],[1,2,3]], [[1,3],[2,0]]),
    (4, "Same Span Obscuration", [[2,4,7],[2,4,5],[2,4,6]], [[2,7],[4,0]]),
    (5, "Exact Duplicate Buildings", [[1,5,3],[1,5,3]], [[1,3],[5,0]]),
    (6, "Interlocking Periodic Skyline", [[0,5,7],[5,10,7],[5,10,12],[10,15,7],[15,20,7],[15,20,12],[20,25,7]], [[0,7],[5,12],[10,7],[15,12],[20,7],[25,0]]),
    (7, "Overlapping Same-Height Cascade", [[0,3,3],[1,5,3],[2,4,3],[3,7,3]], [[0,3],[7,0]]),
    (8, "Dominant Tall Enclosing Shorter", [[1,10,9],[2,5,6],[4,8,7],[6,9,5]], [[1,9],[10,0]]),
    (9, "Disjoint Gapped Towers", [[1,2,1],[3,4,1]], [[1,1],[2,0],[3,1],[4,0]]),
    (10, "Max 32-Bit Integer Coordinates", [[0, 2147483647, 2147483647]], [[0, 2147483647], [2147483647, 0]]),
    (11, "Empty Input Array", [], []),
    (12, "Step Down Junction", [[1,3,4],[3,5,2]], [[1,4],[3,2],[5,0]]),
    (13, "Single Building", [[0, 10, 5]], [[0, 5], [10, 0]]),
    (14, "Nested Stepped Pyramids", [[1,9,2],[2,8,4],[3,7,6],[4,6,8]], [[1,2],[2,4],[3,6],[4,8],[6,6],[7,4],[8,2],[9,0]]),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn([list(b) for b in inp])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 06: LeetCode 480 (Sliding Window Median)
# ==============================================================================
P06_DIR = DECATHLON_ROOT / "problem06_sliding_median"
P06_PROMPT = """Write a production-grade, highly optimized Python implementation of Sliding Window Median (LeetCode 480).

Save your implementation into a single standalone file named `sliding_median.py`.

### Target Function Signature
```python
def median_sliding_window(nums: list[int], k: int) -> list[float]:
    \"\"\"
    Return double-precision floating point medians for each sliding window of size k.
    Must run in strict O(N log K) time using balanced dual-heaps with lazy deletion.
    \"\"\"
```

Output ONLY the complete Python code in `sliding_median.py` without markdown backticks or commentary so it can be written directly to file.
"""

P06_EVALUATOR = """import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p06", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.median_sliding_window

random.seed(42)
S_NUMS = [random.randint(-10000, 10000) for _ in range(30000)]
S_K = 15000

CASES = [
    (1, "Standard Odd Window (k=3)", [1, 3, -1, -3, 5, 3, 6, 7], 3, [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]),
    (2, "Duplicates in Window", [1, 2, 3, 4, 2, 3, 1, 4, 2], 3, [2.0, 3.0, 3.0, 3.0, 2.0, 3.0, 2.0]),
    (3, "Even Window Size (k=4)", [1, 4, 2, 3], 4, [2.5]),
    (4, "Window Size 1 (k=1)", [5], 1, [5.0]),
    (5, "Max 32-bit Addition Overflow", [2147483647, 2147483647], 2, [2147483647.0]),
    (6, "All Negative Integers", [-1, -2, -3, -4, -5], 2, [-1.5, -2.5, -3.5, -4.5]),
    (7, "Uniform Constant Array", [1, 1, 1, 1, 1, 1], 4, [1.0, 1.0, 1.0]),
    (8, "Unsorted Balance Flips", [7, 0, 3, 9, 9, 9, 1, 7, 2, 3], 6, [8.0, 6.0, 8.0, 8.0, 5.0]),
    (9, "Extreme Mixed 32-bit Signs", [-2147483648, -2147483648, 2147483647, -2147483648], 3, [-2147483648.0, -2147483648.0]),
    (10, "Minimal Array (k=1)", [1, 2], 1, [1.0, 2.0]),
    (11, "Full Array Window (k=N)", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10, [5.5]),
    (12, "Stress Test N=30,000, K=15,000", S_NUMS, S_K, None),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, nums, k, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(list(nums), k)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if exp is not None:
                ok = (len(got) == len(exp)) and all(abs(a - b) < 1e-4 for a, b in zip(got, exp))
            else:
                ok = (len(got) == 15001) and abs(got[0] - 87.0) < 1e-4 and abs(got[-1] - (-159.5)) < 1e-4 and elapsed < 2500
            if ok:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 07: LeetCode 847 (Shortest Path Visiting All Nodes)
# ==============================================================================
P07_DIR = DECATHLON_ROOT / "problem07_shortest_path_all_nodes"
P07_PROMPT = """Write a production-grade, highly optimized Python implementation of Shortest Path Visiting All Nodes (LeetCode 847).

Save your implementation into a single standalone file named `shortest_path_nodes.py`.

### Target Function Signature
```python
def shortest_path_length(graph: list[list[int]]) -> int:
    \"\"\"
    You have an undirected, connected graph of n nodes labeled from 0 to n - 1.
    You are given an array graph where graph[i] is a list of all the nodes connected with node i by an edge.
    Return the length of the shortest path that visits every node. You may start and stop at any node,
    you may revisit nodes multiple times, and you may reuse edges.
    \"\"\"
```

### Specifications & Complexity
- Constraints: 1 <= n <= 12.
- Must use Multi-Source Breadth-First Search (BFS) with bitmask state space (u, mask) in $O(n^2 2^n)$ time.
- Any unpruned recursive DFS or brute force TSP will cause Time Limit Exceeded (TLE) or Memory Limit Exceeded (MLE).

Output ONLY the complete Python code in `shortest_path_nodes.py` without markdown backticks or commentary so it can be written directly to file.
"""

P07_EVALUATOR = """import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p07", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.shortest_path_length

CASES = [
    (1, "Linear Chain 4 Nodes", [[1,2,3],[0],[0],[0]], 4),
    (2, "Complete Graph K4", [[1],[0,2,4],[1,3,4],[2],[1,2]], 4),
    (3, "Single Node Graph", [[]], 0),
    (4, "Two Nodes Connected", [[1],[0]], 1),
    (5, "Triangle Cycle K3", [[1,2],[0,2],[0,1]], 2),
    (6, "Ring of 5 Nodes C5", [[1,4],[0,2],[1,3],[2,4],[3,0]], 4),
    (7, "Binary Tree Topology", [[1,2],[0,3,4],[0,5,6],[1],[1],[2],[2]], 8),
    (8, "Star Graph with 6 Nodes", [[1,2,3,4,5],[0],[0],[0],[0],[0]], 9),
    (9, "Path Graph of 6 Nodes", [[1],[0,2],[1,3],[2,4],[3,5],[4]], 5),
    (10, "Bipartite Graph K3,3", [[3,4,5],[3,4,5],[3,4,5],[0,1,2],[0,1,2],[0,1,2]], 5),
    (11, "Dumbbell Graph (Two K3 joined)", [[1,2],[0,2,3],[0,1],[1,4,5],[3,5],[3,4]], 6),
    (12, "Stress Maximum N=12 Path Graph", [[i-1, i+1] if 0 < i < 11 else ([1] if i == 0 else [10]) for i in range(12)], 11),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, g, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn([list(adj) for adj in g])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and elapsed < 1000:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 08: LeetCode 10 (Regular Expression Matching)
# ==============================================================================
P08_DIR = DECATHLON_ROOT / "problem08_regex_matching"
P08_PROMPT = """Write a production-grade, highly optimized Python implementation of Regular Expression Matching (LeetCode 10).

Save your implementation into a single standalone file named `regex_matching.py`.

### Target Function Signature
```python
def is_match(s: str, p: str) -> bool:
    \"\"\"
    Given an input string s and a pattern p, implement regular expression matching with support for '.' and '*' where:
    - '.' Matches any single character.
    - '*' Matches zero or more of the preceding element.
    The matching should cover the entire input string (not partial).
    \"\"\"
```

### Specifications & Complexity
- Must run in $O(M \cdot N)$ using 2D Dynamic Programming or memoized recursion.
- Catastrophic backtracking with overlapping '*' patterns (e.g. `a*a*a*a*a*b`) must terminate in under 5ms.

Output ONLY the complete Python code in `regex_matching.py` without markdown backticks or commentary so it can be written directly to file.
"""

P08_EVALUATOR = """import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p08", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.is_match

CASES = [
    (1, "Basic Mismatch", "aa", "a", False),
    (2, "Basic Kleene Star Match", "aa", "a*", True),
    (3, "Dot Star Universal Match", "ab", ".*", True),
    (4, "Multi Kleene Zero Occurrences", "aab", "c*a*b", True),
    (5, "Subtle Trailing Wildcard", "mississippi", "mis*is*p*.", False),
    (6, "Empty String and Pattern", "", "", True),
    (7, "Empty String with Valid Star", "", "a*", True),
    (8, "Empty String with Unmatched Dot", "", ".", False),
    (9, "Consecutive Redundant Kleene Stars", "ab", ".*..a*", False),
    (10, "Greedy Fallback Match", "aaa", "a*a", True),
    (11, "Dot Star Backtracking Match", "ab", ".*..", True),
    (12, "Catastrophic Backtracking Stress", "aaaaaaaaaaaaaaaaaaab", "a*a*a*a*a*a*a*a*a*a*c", False),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, s, p, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(s, p)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and elapsed < 100:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 09: LeetCode 312 (Burst Balloons)
# ==============================================================================
P09_DIR = DECATHLON_ROOT / "problem09_burst_balloons"
P09_PROMPT = """Write a production-grade, highly optimized Python implementation of Burst Balloons (LeetCode 312).

Save your implementation into a single standalone file named `burst_balloons.py`.

### Target Function Signature
```python
def max_coins(nums: list[int]) -> int:
    \"\"\"
    You are given n balloons, indexed from 0 to n - 1. Each balloon is painted with a number on it
    represented by an array nums. You are asked to burst all the balloons.
    If you burst the i-th balloon, you will get nums[i - 1] * nums[i] * nums[i + 1] coins.
    If i - 1 or i + 1 goes out of bounds, treat it as if there is a balloon with a 1 painted on it.
    Return the maximum coins you can collect by bursting the balloons wisely.
    \"\"\"
```

### Specifications & Complexity
- Constraints: 1 <= nums.length <= 300, 0 <= nums[i] <= 100.
- Must run in $O(N^3)$ time using reverse interval Dynamic Programming (evaluating which balloon is popped *last* in interval `[i, j]`).
- Forward simulation or brute-force backtracking will cause TLE.

Output ONLY the complete Python code in `burst_balloons.py` without markdown backticks or commentary so it can be written directly to file.
"""

P09_EVALUATOR = """import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p09", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.max_coins

random.seed(42)
S_NUMS = [random.randint(1, 100) for _ in range(120)]

CASES = [
    (1, "Standard 4 Balloons", [3, 1, 5, 8], 167),
    (2, "Two Balloons", [1, 5], 10),
    (3, "Single Balloon", [7], 7),
    (4, "All 1s Array", [1, 1, 1, 1], 4),
    (5, "Array with Zeroes", [0, 5, 0], 5),
    (6, "Alternating Values", [2, 4, 2, 4, 2], 64),
    (7, "Strictly Increasing", [1, 2, 3, 4, 5], 110),
    (8, "Strictly Decreasing", [5, 4, 3, 2, 1], 110),
    (9, "Identical High Numbers", [9, 9, 9], 819),
    (10, "Balloons with Zero Outer", [0, 8, 8, 0], 80),
    (11, "Ten Random Elements", [8, 2, 6, 4, 1, 3, 9, 7, 5, 2], 1269),
    (12, "Stress Scale N=120 Balloons", S_NUMS, None),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(list(inp))
            elapsed = (time.perf_counter() - t0) * 1000.0
            ok = (got == exp) if exp is not None else (isinstance(got, int) and got > 0 and elapsed < 1500)
            if ok:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

# ==============================================================================
# PROBLEM 10: LeetCode 407 (Trapping Rain Water II)
# ==============================================================================
P10_DIR = DECATHLON_ROOT / "problem10_trapping_rain_3d"
P10_PROMPT = """Write a production-grade, highly optimized Python implementation of Trapping Rain Water II (LeetCode 407).

Save your implementation into a single standalone file named `trapping_rain_3d.py`.

### Target Function Signature
```python
def trap_rain_water(height_map: list[list[int]]) -> int:
    \"\"\"
    Given an m x n integer matrix height_map representing the height of each unit cell in a 2D elevation map,
    return the volume of water it can trap after raining.
    \"\"\"
```

### Specifications & Complexity
- Constraints: 1 <= m, n <= 200, 0 <= height_map[i][j] <= 2 * 10^4.
- Must use a 3D Priority-Queue / Dijkstra boundary shrinking algorithm in $O(M \cdot N \log(M \cdot N))$ time.
- Push all perimeter cells into min-heap; pop minimum boundary height and flood-fill neighbors.

Output ONLY the complete Python code in `trapping_rain_3d.py` without markdown backticks or commentary so it can be written directly to file.
"""

P10_EVALUATOR = """import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p10", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.trap_rain_water

random.seed(42)
S_MAP = [[random.randint(1, 100) for _ in range(80)] for _ in range(80)]
for r in range(80):
    for c in range(80):
        if r == 0 or r == 79 or c == 0 or c == 79:
            S_MAP[r][c] = 500

CASES = [
    (1, "Standard 3x6 Bowl", [[1,4,3,1,3,2],[3,2,1,3,2,4],[2,3,3,2,3,1]], 4),
    (2, "Multi-level 5x5 Matrix", [[3,3,3,3,3],[3,2,2,2,3],[3,2,1,2,3],[3,2,2,2,3],[3,3,3,3,3]], 10),
    (3, "Degenerate 1x1 Matrix", [[5]], 0),
    (4, "Degenerate 2x2 Matrix", [[1,2],[3,4]], 0),
    (5, "Flat Elevation Grid", [[2,2,2],[2,2,2],[2,2,2]], 0),
    (6, "Sloped Incline (No Trapping)", [[1,2,3],[4,5,6],[7,8,9]], 0),
    (7, "Single Deep Basin", [[10,10,10],[10,0,10],[10,10,10]], 10),
    (8, "Multiple Disjoint Pits", [[5,5,5,5,5],[5,1,5,1,5],[5,5,5,5,5]], 8),
    (9, "Thin Wall Leakage", [[5,5,5,5],[5,0,0,1],[5,5,5,5]], 2),
    (10, "Perimeter High Wall Bowl", [[9,9,9],[9,1,9],[9,9,9]], 8),
    (11, "Zero Elevation Pit", [[0,0,0],[0,0,0],[0,0,0]], 0),
    (12, "Stress 80x80 Fortified Reservoir", S_MAP, None),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, hmap, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn([list(r) for r in hmap])
            elapsed = (time.perf_counter() - t0) * 1000.0
            ok = (got == exp) if exp is not None else (isinstance(got, int) and got > 0 and elapsed < 1500)
            if ok:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
"""

CONFIGS = [
    (P01_DIR, P01_PROMPT, P01_EVALUATOR),
    (P02_DIR, P02_PROMPT, P02_EVALUATOR),
    (P03_DIR, P03_PROMPT, P03_EVALUATOR),
    (P04_DIR, P04_PROMPT, P04_EVALUATOR),
    (P05_DIR, P05_PROMPT, P05_EVALUATOR),
    (P06_DIR, P06_PROMPT, P06_EVALUATOR),
    (P07_DIR, P07_PROMPT, P07_EVALUATOR),
    (P08_DIR, P08_PROMPT, P08_EVALUATOR),
    (P09_DIR, P09_PROMPT, P09_EVALUATOR),
    (P10_DIR, P10_PROMPT, P10_EVALUATOR),
]

def main():
    print("Setting up 10 Hardest Algorithmic Problems...")
    for pdir, prompt, evaluator in CONFIGS:
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "etta_ws").mkdir(exist_ok=True)
        (pdir / "agy_ws").mkdir(exist_ok=True)
        (pdir / "PROMPT.md").write_text(prompt, encoding="utf-8")
        (pdir / "evaluator.py").write_text(evaluator, encoding="utf-8")
        print(f"  ✅ Configured {pdir.name}")
    print("All 10 problem suites initialized successfully!")

if __name__ == "__main__":
    main()
