import sys, time, importlib.util
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
    (8, "k=5 eggs, n=200 floors", 5, 200, 8),
    (9, "k=10 eggs, n=1000 floors", 10, 1000, 10),
    (10, "k=3 eggs, n=26 floors", 3, 26, 6),
    (11, "k=7 eggs, n=5000 floors", 7, 5000, 13),
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
