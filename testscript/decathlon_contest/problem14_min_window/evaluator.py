import sys, time, random, string, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p14", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.min_window

random.seed(42)
S_CHARS = string.ascii_letters
S_LARGE_S = "".join(random.choices(S_CHARS, k=100000)) + "XYZW" + "".join(random.choices(S_CHARS, k=1000))
S_LARGE_T = "XYZW"

CASES = [
    (1, "Standard Mixed Example", "ADOBECODEBANC", "ABC", "BANC"),
    (2, "Single Character Exact Match", "a", "a", "a"),
    (3, "Single Character Mismatch", "a", "aa", ""),
    (4, "Exact Whole String Match", "abc", "abc", "abc"),
    (5, "Multiple Identical in Target", "aab", "aa", "aa"),
    (6, "Duplicates in Source With Shorter Later", "bba", "ab", "ba"),
    (7, "Target Longer Than Source", "a", "ab", ""),
    (8, "Minimum Window At Start", "abcde", "ab", "ab"),
    (9, "Minimum Window At End", "xyzab", "ab", "ab"),
    (10, "Case Sensitivity Distinction", "aA", "Aa", "aA"),
    (11, "Repeated Target Pattern In Source", "cabwefgewcwaefgcf", "cae", "cwae"),
    (12, "Stress Scale |S|=100k, |T|=4", S_LARGE_S, S_LARGE_T, "XYZW"),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, s, t, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(s, t)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and (num != 12 or elapsed < 200):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL (exp '{exp}', got '{got}')")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
