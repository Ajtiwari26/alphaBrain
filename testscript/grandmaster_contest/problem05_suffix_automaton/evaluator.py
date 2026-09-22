import sys, time, random, string, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("g05", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.shortest_unique_common_substring

def ref_sam(s1, s2):
    n1, n2 = len(s1), len(s2)
    s = s1 + "#" + s2 + "$"
    n = len(s)

    MAXLEN = [0] * (2 * n)
    LINK = [0] * (2 * n)
    NEXT = [{} for _ in range(2 * n)]
    LINK[0] = -1
    sz = 1
    last = 0
    pos = [[] for _ in range(2 * n)]

    for i, ch in enumerate(s):
        cur = sz
        sz += 1
        MAXLEN[cur] = MAXLEN[last] + 1
        pos[cur].append(i)
        p = last
        while p != -1 and ch not in NEXT[p]:
            NEXT[p][ch] = cur
            p = LINK[p]
        if p == -1:
            LINK[cur] = 0
        else:
            q = NEXT[p][ch]
            if MAXLEN[p] + 1 == MAXLEN[q]:
                LINK[cur] = q
            else:
                clone = sz
                sz += 1
                MAXLEN[clone] = MAXLEN[p] + 1
                NEXT[clone] = NEXT[q].copy()
                LINK[clone] = LINK[q]
                while p != -1 and NEXT[p].get(ch) == q:
                    NEXT[p][ch] = clone
                    p = LINK[p]
                LINK[q] = LINK[cur] = clone
        last = cur

    order = sorted(range(sz), key=lambda x: MAXLEN[x], reverse=True)
    c1 = [0] * sz
    c2 = [0] * sz

    for u in order:
        for idx in pos[u]:
            if idx < n1:
                c1[u] += 1
            elif n1 < idx < n1 + 1 + n2:
                c2[u] += 1
        if LINK[u] != -1:
            c1[LINK[u]] += c1[u]
            c2[LINK[u]] += c2[u]

    ans = float("inf")
    for u in range(1, sz):
        if c1[u] == 1 and c2[u] == 1:
            ans = min(ans, MAXLEN[LINK[u]] + 1)

    return ans if ans != float("inf") else -1

random.seed(42)
S_CHARS = string.ascii_lowercase
S_L1 = "".join(random.choices(S_CHARS, k=5000)) + "xyzunique" + "".join(random.choices(S_CHARS, k=5000))
S_L2 = "".join(random.choices(S_CHARS, k=5000)) + "xyzunique" + "".join(random.choices(S_CHARS, k=5000))
S_EXP = ref_sam(S_L1, S_L2)

CASES = [
    (1, "CF 427D Sample 1 (apple, pebble)", "apple", "pebble", 1),
    (2, "No Common Substring (abc, def)", "abc", "def", -1),
    (3, "CF 427D Sample 3 (banana, cabana)", "banana", "cabana", 1),
    (4, "Single Character Disjoint (a, b)", "a", "b", -1),
    (5, "Repeated Duplicates (aa, aa)", "aa", "aa", 2),
    (6, "Prefix Match Only (abcdef, abczxy)", "abcdef", "abczxy", 1),
    (7, "Whole String Unique Match", "unique", "unique", 1),
    (8, "Periodic String Trap (ababab, bababa)", "ababab", "bababa", ref_sam("ababab", "bababa")),
    (9, "One Unique in Long Repeating (aaaaXaaaa, bbbbXbbbb)", "aaaaXaaaa", "bbbbXbbbb", 1),
    (10, "Medium Random Strings N=1,000", S_L1[:1000], S_L2[:1000], ref_sam(S_L1[:1000], S_L2[:1000])),
    (11, "Stress Scale |S1|=|S2|=10,000", S_L1, S_L2, S_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, s1, s2, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(s1, s2)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Scale test must complete in < 350ms, strictly disqualifying O(N^2)
            if got == exp and (num != 11 or elapsed < 350):
                print(f"[OK ] Case {num:02d}: {name:<40} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<40} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<40} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
