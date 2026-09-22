import sys, time, random, importlib.util
from collections import deque
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("g04", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.min_logging_cost

def ref_cht(a, b):
    n = len(a)
    if n <= 1:
        return 0
    q = deque()
    q.append((b[0], 0))
    dp = 0
    for i in range(1, n):
        x = a[i]
        while len(q) >= 2:
            m1, c1 = q[0]
            m2, c2 = q[1]
            if m1 * x + c1 >= m2 * x + c2:
                q.popleft()
            else:
                break
        best_m, best_c = q[0]
        dp = best_m * x + best_c

        new_m, new_c = b[i], dp
        while len(q) >= 2:
            m2, c2 = q[-1]
            m1, c1 = q[-2]
            if (c2 - c1) * (m2 - new_m) >= (new_c - c2) * (m1 - m2):
                q.pop()
            else:
                break
        q.append((new_m, new_c))
    return dp

random.seed(42)
S_A = [1] + sorted(random.sample(range(2, 500000), 49998)) + [1000000]
S_B = sorted(random.sample(range(1, 500000), 49999), reverse=True) + [0]
S_EXP = ref_cht(S_A, S_B)

CASES = [
    (1, "CF 319C Sample 1", [1, 2, 3, 4, 5], [5, 4, 3, 2, 0], 25),
    (2, "CF 319C Sample 2", [1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 0], 36),
    (3, "Minimal Length N=2", [1, 10], [5, 0], 50),
    (4, "Large Coordinate Jump", [1, 100, 10000], [1000, 10, 0], ref_cht([1, 100, 10000], [1000, 10, 0])),
    (5, "Flat Slopes Adjacent", [1, 2, 3, 4], [10, 9, 8, 0], ref_cht([1, 2, 3, 4], [10, 9, 8, 0])),
    (6, "Uniform Linear Increments", [1, 3, 5, 7, 9], [8, 6, 4, 2, 0], ref_cht([1, 3, 5, 7, 9], [8, 6, 4, 2, 0])),
    (7, "N=10 Geometric Scale", [1, 2, 4, 8, 16, 32, 64, 128, 256, 512], [512, 256, 128, 64, 32, 16, 8, 4, 2, 0], ref_cht([1, 2, 4, 8, 16, 32, 64, 128, 256, 512], [512, 256, 128, 64, 32, 16, 8, 4, 2, 0])),
    (8, "Medium Random N=1,000", S_A[:1000], S_B[:999] + [0], ref_cht(S_A[:1000], S_B[:999] + [0])),
    (9, "Stress Scale N=50,000", S_A, S_B, S_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, a, b, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(list(a), list(b))
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Scale test must complete in < 200ms, strictly disqualifying O(N^2)
            if got == exp and (num != 9 or elapsed < 200):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
