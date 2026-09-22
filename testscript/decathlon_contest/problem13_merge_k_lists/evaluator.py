import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p13", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.merge_k_lists

random.seed(42)
S_LISTS = [[random.randint(-1000, 1000) for _ in range(100)] for _ in range(500)]
for sub in S_LISTS:
    sub.sort()
S_EXP = sorted([x for sub in S_LISTS for x in sub])

CASES = [
    (1, "Standard 3 Lists", [[1, 4, 5], [1, 3, 4], [2, 6]], [1, 1, 2, 3, 4, 4, 5, 6]),
    (2, "Empty Input List", [], []),
    (3, "Single Empty Sublist", [[]], []),
    (4, "Multiple Empty Sublists", [[], [], []], []),
    (5, "Mixed Empty and Non-Empty", [[], [1], [], [0, 2]], [0, 1, 2]),
    (6, "Single Populated List", [[1, 2, 3]], [1, 2, 3]),
    (7, "50 Disjoint Singletons", [[i] for i in range(50, 0, -1)], list(range(1, 51))),
    (8, "Duplicate Elements Across Lists", [[1, 1], [1, 1], [1]], [1, 1, 1, 1, 1]),
    (9, "Negative Monotonic Lists", [[-10, -5], [-8, -2], [-1]], [-10, -8, -5, -2, -1]),
    (10, "Skewed List Sizes (1000 vs 1s)", [list(range(1000)), [5], [15], [25]], sorted(list(range(1000)) + [5, 15, 25])),
    (11, "Disjoint Sequential Blocks", [[1, 2, 3], [4, 5, 6], [7, 8, 9]], list(range(1, 10))),
    (12, "Stress Scale k=500, N=50k", S_LISTS, S_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, exp in CASES:
        t0 = time.perf_counter()
        try:
            # pass deepcopy-like clone
            got = fn([list(sub) for sub in inp])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and (num != 12 or elapsed < 500):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
