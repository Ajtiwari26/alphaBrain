import sys, time, random, importlib.util
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
