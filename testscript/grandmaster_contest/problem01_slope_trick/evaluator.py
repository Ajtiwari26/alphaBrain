import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("g01", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.min_operations_increasing

# Ground-truth reference implementation via verified Slope Trick
def ref_slope_trick(nums):
    import heapq
    n = len(nums)
    if n <= 1:
        return 0
    a = [nums[i] - i for i in range(n)]
    heap = []
    ans = 0
    for x in a:
        heapq.heappush(heap, -x)
        top = -heap[0]
        if top > x:
            ans += top - x
            heapq.heappop(heap)
            heapq.heappush(heap, -x)
    return ans

random.seed(42)
S_NUMS = [random.randint(-100000, 100000) for _ in range(50000)]
S_EXP = ref_slope_trick(S_NUMS)

CASES = [
    (1, "Already Strictly Increasing", [1, 2, 3, 4, 5], 0),
    (2, "Strictly Decreasing 5 to 1", [5, 4, 3, 2, 1], 12),
    (3, "Codeforces 713C Sample 1", [2, 1, 5, 11, 5, 9, 11], 9),
    (4, "Codeforces 713C Sample 2", [5, 4, 4, 5], 4),
    (5, "Singleton Element", [100], 0),
    (6, "Uniform Identical Elements", [7, 7, 7, 7, 7], 6),
    (7, "Alternating High-Low Spikes", [1, 100, 2, 100, 3], ref_slope_trick([1, 100, 2, 100, 3])),
    (8, "Two Elements Inverted", [2, 1], 2),
    (9, "Negative Monotonic Range", [-5, -10, -2, -1], ref_slope_trick([-5, -10, -2, -1])),
    (10, "Extreme Jump Values", [1, 1000000, 2], ref_slope_trick([1, 1000000, 2])),
    (11, "Medium Random Array N=1,000", S_NUMS[:1000], ref_slope_trick(S_NUMS[:1000])),
    (12, "Stress Scale N=50,000", S_NUMS, S_EXP),
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
            # Scale test must complete in < 250ms, strictly disqualifying O(N^2)
            if got == exp and (num != 12 or elapsed < 250):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
