import sys, time, random, importlib.util
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
    (6, "Alternating Values", [2, 4, 2, 4, 2], 86),
    (7, "Strictly Increasing", [1, 2, 3, 4, 5], 110),
    (8, "Strictly Decreasing", [5, 4, 3, 2, 1], 110),
    (9, "Identical High Numbers", [9, 9, 9], 819),
    (10, "Balloons with Zero Outer", [0, 8, 8, 0], 72),
    (11, "Ten Random Elements", [8, 2, 6, 4, 1, 3, 9, 7, 5, 2], 1752),
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
