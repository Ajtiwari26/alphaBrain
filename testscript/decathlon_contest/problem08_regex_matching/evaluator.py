import sys, time, importlib.util
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
    (9, "Consecutive Redundant Kleene Stars", "ab", ".*..a*", True),
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
