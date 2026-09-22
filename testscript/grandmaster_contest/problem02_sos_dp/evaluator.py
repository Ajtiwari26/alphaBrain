import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("g02", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.find_compatible_numbers

def ref_sos_dp(nums, B=18):
    max_val = 1 << B
    dp = [-1] * max_val
    for x in nums:
        dp[x] = x
    for i in range(B):
        bit = 1 << i
        for mask in range(max_val):
            if mask & bit:
                if dp[mask] == -1:
                    dp[mask] = dp[mask ^ bit]
    full = max_val - 1
    res = []
    for x in nums:
        comp = full ^ x
        res.append(dp[comp])
    return res

random.seed(42)
S_NUMS = [random.randint(0, (1 << 18) - 1) for _ in range(50000)]
S_EXP = ref_sos_dp(S_NUMS, 18)

CASES = [
    (1, "CF 165E Sample [2, 3, 4]", [2, 3, 4], True),
    (2, "Mutually Incompatible All Bits", [262143, 262143, 262143], False),
    (3, "Zero Element Universal Match", [0, 1, 2, 3], True),
    (4, "Orthogonal Powers of Two", [1, 2, 4, 8, 16], True),
    (5, "Dense Interleaved Masks", [5, 10, 15, 20], True),
    (6, "Alternating Odd/Even", [1, 3, 5, 7, 2, 4, 6, 8], True),
    (7, "Single Pair Complement", [12345, 262143 ^ 12345], True),
    (8, "Sparse Non-overlapping", [1 << 0, 1 << 17], True),
    (9, "No Compatible Candidates", [262143, 262142, 262141], False),
    (10, "Medium Random N=1,000", S_NUMS[:1000], True),
    (11, "Stress Scale N=50,000", S_NUMS, True),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, inp, has_matches in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(list(inp))
            elapsed = (time.perf_counter() - t0) * 1000.0

            # Verify correctness: for each element, if got[i] != -1, verify (inp[i] & got[i]) == 0 and got[i] in inp
            inp_set = set(inp)
            valid = len(got) == len(inp)
            for x, y in zip(inp, got):
                if y != -1:
                    if (x & y) != 0 or y not in inp_set:
                        valid = False
                        break

            if valid and (num != 11 or elapsed < 900):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
