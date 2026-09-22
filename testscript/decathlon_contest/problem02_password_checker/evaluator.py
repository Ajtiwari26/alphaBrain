import sys, time, importlib.util
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
    (15, "Long Modulo-2 Cascade", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 16),
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
