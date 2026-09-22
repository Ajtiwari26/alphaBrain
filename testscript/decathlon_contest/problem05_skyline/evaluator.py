import sys, time, importlib.util
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
