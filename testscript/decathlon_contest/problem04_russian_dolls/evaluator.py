import sys, time, random, importlib.util
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
